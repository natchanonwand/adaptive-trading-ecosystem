"""Bounded polling, atomic persistence, history overlap and broker-first reconciliation."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from sqlalchemy import Engine

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring.contracts import (
    AccountView,
    ActivityView,
    Environment,
    EventType,
    HealthView,
    PortfolioView,
    PositionView,
    Scope,
)
from trading_ecosystem.mt5.client import Mt5ReadClient, ReadError, Record
from trading_ecosystem.mt5.config import BridgeConfig
from trading_ecosystem.mt5.economics import inspect_instrument
from trading_ecosystem.mt5.mapping import account_view, position_view
from trading_ecosystem.mt5.normalization import (
    account_identity,
    history_key,
    identity,
    normalize,
    number,
    timestamp,
)
from trading_ecosystem.mt5.store import Store


class ConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    STALE = "STALE"
    ERROR = "ERROR"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class QualificationRefused(RuntimeError):
    pass


class Bridge:
    def __init__(self, client: Mt5ReadClient, engine: Engine, config: BridgeConfig) -> None:
        self.client, self.engine, self.config = client, engine, config
        self.scope = Scope(environment=Environment.DEMO, run_id=identity("MT5_READONLY_SERVICE"))
        self.state = ConnectionState.DISCONNECTED
        self.due: dict[str, datetime] = {}
        self.retry_at: datetime | None = None
        self.failures = 0
        self.attached = False
        self.refused = False
        self.stage = "connection"

    def health(
        self,
        store: Store,
        component: Literal[
            "broker", "market_data", "system", "reconciliation", "portfolio", "database"
        ],
        state: Literal["HEALTHY", "DEGRADED", "STALE", "DISCONNECTED", "ERROR"],
        detail: str,
        at: datetime,
    ) -> None:
        payload = HealthView(component=component, state=state, detail=detail)
        store.emit(EventType.SYSTEM_HEALTH, payload, at)

    def _failure(self, at: datetime, reason: str) -> None:
        self.state = ConnectionState.ERROR
        with self.engine.begin() as conn:
            store = Store(conn, self.scope)
            self.health(store, "broker", "DISCONNECTED", reason, at)
            self.health(store, "market_data", "STALE", "QUOTE_STALE; BRIDGE_DISCONNECTED", at)
            store.state.pop("quote_health", None)
            if self.stage == "history":
                self.health(store, "system", "ERROR", "HISTORY_SYNC_ERROR; CURSOR_UNCHANGED", at)
            if store.state.get("account_payload"):
                stale = dict(store.state["account_payload"])
                stale["stale"] = True
                store.emit(EventType.ACCOUNT_SNAPSHOT, AccountView.model_validate(stale), at)
                store.state["account_hash"] = None
                self.health(store, "portfolio", "STALE", "ACCOUNT_STALE", at)
            store.save()
        self.client.shutdown()
        self.attached = False
        self.failures += 1
        seconds = min(
            self.config.retry_cap_seconds,
            self.config.retry_seconds * 2 ** min(self.failures - 1, 10),
        )
        self.retry_at = at + timedelta(seconds=seconds)

    def _validate_account(self, account: Record) -> None:
        if type(account.get("trade_mode")) is not int or account.get("trade_mode") != 0:
            self.refused = True
            raise QualificationRefused("REAL_OR_UNKNOWN_ACCOUNT_REFUSED")
        if account.get("currency") != "USD":
            self.refused = True
            raise QualificationRefused("NON_USD_ACCOUNT_DISPLAY_NOT_QUALIFIED")

    def step(self, at: datetime) -> bool:
        if self.refused or self.retry_at is not None and at < self.retry_at:
            return False
        try:
            if not self.attached:
                self.state = ConnectionState.CONNECTING
                if not self.client.initialize():
                    raise ReadError("MT5_INITIALIZE_FAILED")
                self.attached = True
                account = self.client.account_info()
                self._validate_account(account)
                self.scope = Scope(
                    environment=Environment.DEMO, account_id=account_identity(account)
                )
                catalog = self.client.symbols_get()
                available = {row["name"] for row in catalog}
                if not set(self.config.aliases.values()) <= available:
                    raise ReadError("EXPLICIT_ALIAS_NOT_IN_BROKER_CATALOG")
                self.due.clear()
            terminal = self.client.terminal_info()
            if terminal.get("connected") is not True:
                raise ReadError("MT5_DISCONNECTED")
            # Verify mode/scope on every cycle; never mix a terminal account switch.
            account = self.client.account_info()
            self._validate_account(account)
            if account_identity(account) != self.scope.account_id:
                raise ReadError("MT5_ACCOUNT_SWITCH_RECONNECT_REQUIRED")
            with self.engine.begin() as conn:
                store = Store(conn, self.scope)
                old_aliases = store.state.get("aliases")
                if old_aliases is not None and old_aliases != self.config.aliases:
                    raise ReadError("PERSISTED_ALIAS_CHANGE_REQUIRES_REVIEW")
                store.state["aliases"] = self.config.aliases
                if self._ready("account", at):
                    self.stage = "account"
                    self._account(store, account, at)
                if self._ready("positions", at):
                    self.stage = "positions"
                    self._positions(store, self.client.positions_get(), at)
                    self.stage = "orders"
                    self._orders(store, self.client.orders_get(), at)
                if self._ready("quotes", at):
                    self.stage = "quotes"
                    self._quotes(store, at)
                if self._ready("metadata", at):
                    self.stage = "metadata"
                    self._metadata(store, account, at)
                if self._ready("history", at):
                    self.stage = "history"
                    self._history(store, at)
                if self._ready("health", at):
                    store.observation("TERMINAL", "current", normalize(terminal), at)
                    self.health(store, "broker", "HEALTHY", "MT5_CONNECTED; READ_ONLY", at)
                    self.health(store, "portfolio", "HEALTHY", "ACCOUNT_FRESH", at)
                    quote_health = store.state.get("quote_health", "QUOTE_STALE")
                    self.health(
                        store,
                        "market_data",
                        "STALE" if quote_health.startswith("QUOTE_STALE") else "HEALTHY",
                        quote_health,
                        at,
                    )
                    self.health(store, "database", "HEALTHY", "MONITORING_TRANSACTION_OK", at)
                store.save()
            self.stage = "connection"
            self.state = (
                ConnectionState.STALE
                if store.state.get("quote_health", "").startswith("QUOTE_STALE")
                else ConnectionState.CONNECTED
            )
            self.failures, self.retry_at = 0, None
            return True
        except QualificationRefused as error:
            self._failure(at, str(error))
            return False
        except (ReadError, ValueError, KeyError, TypeError) as error:
            self._failure(
                at,
                str(error)
                if isinstance(error, ReadError)
                else "MT5_ERROR; OBSERVATION_CYCLE_ROLLED_BACK",
            )
            self.due.clear()
            return False

    def _ready(self, kind: str, at: datetime) -> bool:
        if kind in self.due and at < self.due[kind]:
            return False
        seconds = {
            "account": self.config.account_seconds,
            "positions": self.config.positions_seconds,
            "quotes": self.config.quotes_seconds,
            "health": self.config.health_seconds,
            "history": self.config.history_seconds,
            "metadata": self.config.metadata_seconds,
        }[kind]
        self.due[kind] = at + timedelta(seconds=seconds)
        return True

    def _account(self, store: Store, row: Record, at: datetime) -> None:
        body = normalize(row)
        changed = digest(canonical_bytes(body)) != store.state.get("account_hash")
        if changed:
            store.observation("ACCOUNT", "current", body, at)
            store.emit(EventType.ACCOUNT_SNAPSHOT, account_view(row), at)
            store.state["account_hash"] = digest(canonical_bytes(body))
            store.state["account_payload"] = account_view(row).model_dump(mode="json")

    def _logical(self, broker: str) -> str:
        return next((k for k, v in self.config.aliases.items() if v == broker), broker)

    def _positions(self, store: Store, rows: tuple[Record, ...], at: datetime) -> None:
        previous: Record = store.state.get("positions", {})
        generations: Record = store.state.get("position_generations", {})
        current: Record = {}
        projected = store.projected_positions()
        expected = {entry["payload"]["episode_id"]: entry["payload"] for entry in previous.values()}
        mismatch = set(projected) != set(expected) or any(
            any(projected.get(key, {}).get(field) != value for field, value in body.items())
            for key, body in expected.items()
        )
        if mismatch:
            store.emit(
                EventType.RECONCILIATION_MISMATCH,
                HealthView(
                    component="reconciliation",
                    state="ERROR",
                    detail="READ_MODEL_DIFFERS_FROM_LAST_BROKER_SNAPSHOT; REPLAYING",
                ),
                at,
            )
            store.journal.rebuild(self.scope.stream_id)
            projected = store.projected_positions()
        for native in rows:
            row = normalize(native)
            key = str(row["identifier"])
            if key in current:
                raise ValueError("DUPLICATE_POSITION_IDENTITY")
            old = previous.get(key)
            # A netting reversal/ticket transition is a new observed lifecycle, never a fake fill.
            if old and any(
                old["raw"].get(k) != row.get(k)
                for k in ("ticket", "type", "magic", "symbol", "time_msc")
            ):
                self._close(store, old, at)
                old = None
            if old is None:
                generations[key] = generations.get(key, 0) + 1
            payload = position_view(self.scope.account_id, row, at, generations[key])
            body_hash = digest(canonical_bytes(row))
            if old is None or old["hash"] != body_hash:
                store.observation("POSITION", key, row, at)
                store.emit(
                    EventType.POSITION_OPENED if old is None else EventType.POSITION_UPDATED,
                    payload,
                    at,
                    self._logical(row["symbol"]),
                    row,
                )
            else:
                payload = PositionView.model_validate(old["payload"])
            current[key] = {
                "raw": row,
                "payload": payload.model_dump(mode="json"),
                "hash": body_hash,
            }
        for key, old in previous.items():
            if key not in current:
                self._close(store, old, at)
        changed = previous != current
        if changed or "positions" not in store.state:
            store.emit(
                EventType.RECONCILIATION_OK,
                HealthView(
                    component="reconciliation",
                    state="HEALTHY",
                    detail="OBSERVED_OPEN_POSITION_SET_RECONCILED",
                ),
                at,
            )
        store.state["positions"], store.state["position_generations"] = current, generations
        portfolio = PortfolioView(
            account=AccountView.model_validate(store.state["account_payload"]),
            gross_exposure=None,
            open_risk=None,
            reserved_risk=None,
            daily_pnl=None,
            peak_nav=None,
            drawdown=None,
            risk_state=None,
            open_positions=len(rows),
            reserved_positions=None,
        )
        portfolio_hash = digest(canonical_bytes(portfolio.model_dump()))
        if store.state.get("portfolio_hash") != portfolio_hash:
            store.emit(EventType.PORTFOLIO_SNAPSHOT, portfolio, at)
            store.state["portfolio_hash"] = portfolio_hash

    def _close(self, store: Store, old: Record, at: datetime) -> None:
        body = dict(old["payload"])
        body.update(
            quantity="0",
            state="CLOSED",
            updated_at=at,
            unrealized_pnl=None,
            realized_pnl=None,
            mark_price=None,
            trade=None,
        )
        store.emit(
            EventType.POSITION_CLOSED,
            PositionView.model_validate(body),
            at,
            self._logical(old["raw"]["symbol"]),
            old["raw"],
        )

    def _orders(self, store: Store, rows: tuple[Record, ...], at: datetime) -> None:
        body = {str(row["ticket"]): normalize(row) for row in rows}
        if store.state.get("orders") != body:
            store.observation("PENDING_ORDERS", "current", body, at)
            store.emit(
                EventType.EXTERNAL_OBSERVATION,
                ActivityView(
                    status="PENDING_ORDERS_OBSERVED", domain_identity=digest(canonical_bytes(body))
                ),
                at,
            )
            store.emit(
                EventType.SYSTEM_HEALTH,
                HealthView(
                    component="system",
                    state="HEALTHY",
                    detail=f"PENDING_ORDERS_OBSERVED={len(rows)}; NOT_POSITIONS",
                ),
                at,
            )
            store.state["orders"] = body

    def _quotes(self, store: Store, at: datetime) -> None:
        stale = []
        for logical, broker in self.config.aliases.items():
            row = normalize(self.client.symbol_info_tick(broker))
            source_at = timestamp(row["time"], row.get("time_msc"))
            bid, ask = number(row["bid"]), number(row["ask"])
            if bid <= 0 or ask < bid or source_at > at + timedelta(seconds=5):
                raise ReadError("INVALID_BROKER_QUOTE")
            is_stale = (at - source_at).total_seconds() > self.config.stale_seconds
            if is_stale:
                stale.append(logical)
            # Poll sampling, not tick recording; unchanged ticks deduplicate by source identity.
            with arithmetic_context():
                row["spread"] = str(ask - bid)
            if store.observation("QUOTE", broker, row, at):
                store.emit(
                    EventType.EXTERNAL_OBSERVATION,
                    ActivityView(
                        status="QUOTE_OBSERVED", domain_identity=digest(canonical_bytes(row))
                    ),
                    at,
                    logical,
                )
        state: Literal["STALE", "HEALTHY"] = "STALE" if stale else "HEALTHY"
        message = "QUOTE_STALE: " + ",".join(stale) if stale else "QUOTE_FRESH"
        if store.state.get("quote_health") != message:
            self.health(store, "market_data", state, message, at)
            store.state["quote_health"] = message

    def _metadata(self, store: Store, account: Record, at: datetime) -> None:
        statuses: list[str] = []
        for logical, broker in self.config.aliases.items():
            try:
                row = self.client.symbol_info(broker)
            except ReadError:
                row = None
            snapshot = inspect_instrument(logical, broker, row, at, account["currency"])
            body = snapshot.model_dump(mode="json")
            # Observation timestamp is metadata provenance, not a meaningful-state change.
            store.observation("INSTRUMENT", broker, body, at)
            store.emit(
                EventType.EXTERNAL_OBSERVATION,
                ActivityView(
                    status="INSTRUMENT_OBSERVED", domain_identity=digest(canonical_bytes(body))
                ),
                at,
                logical,
            )
            statuses.append(f"{logical}={snapshot.status}")
        self.health(store, "system", "DEGRADED", "ECONOMICS_PARTIAL; " + "; ".join(statuses), at)
        store.state["economics_status"] = "ECONOMICS_PARTIAL; " + "; ".join(statuses)

    def _history(self, store: Store, at: datetime) -> None:
        checkpoint = store.state.get("history_until")
        start = (
            datetime.fromisoformat(checkpoint) - timedelta(seconds=self.config.overlap_seconds)
            if checkpoint
            else at - timedelta(days=self.config.initial_history_days)
        )
        end = min(at, start + timedelta(seconds=self.config.history_window_seconds))
        if end <= start:
            raise ValueError("HISTORY_WINDOW_INVALID")
        deals = self.client.history_deals_get(start, end)
        orders = self.client.history_orders_get(start, end)
        if len(deals) + len(orders) > self.config.max_history_records:
            raise ReadError("HISTORY_WINDOW_LIMIT_REQUIRES_SMALLER_CONFIGURATION")
        watermark = tuple(store.state.get("deal_watermark", (0, 0, 0)))
        for raw in sorted(deals, key=history_key):
            row = normalize(raw)
            key = history_key(row)
            # Arrival order may be late; broker timestamps stay in the raw canonical record.
            if store.observation("DEAL", str(row["ticket"]), row, at, immutable=True):
                store.emit(
                    EventType.EXTERNAL_OBSERVATION,
                    ActivityView(
                        status="BROKER_DEAL_OBSERVED",
                        reference_id=identity(self.scope.account_id, "DEAL", row["ticket"]),
                        domain_identity=digest(canonical_bytes(row)),
                    ),
                    at,
                    self._logical(row["symbol"]) if row.get("symbol") else None,
                    row,
                )
            watermark = max(watermark, key)
        for raw in orders:
            row = normalize(raw)
            store.observation("HISTORY_ORDER", str(row["ticket"]), row, at)
        store.state["deal_watermark"] = list(watermark)
        store.state["history_until"] = end.isoformat()
        store.state["history_from"] = store.state.get("history_from", start.isoformat())
        self.health(
            store,
            "system",
            "DEGRADED" if store.state.get("economics_status") else "HEALTHY",
            ("HISTORY_SYNC_OK" if end == at else "HISTORY_SYNC_OK; BACKFILL_PENDING")
            + "; "
            + store.state.get("economics_status", "ECONOMICS_UNAVAILABLE"),
            at,
        )

    def stop(self, at: datetime) -> None:
        self.state = ConnectionState.SHUTTING_DOWN
        try:
            with self.engine.begin() as conn:
                store = Store(conn, self.scope)
                self.health(store, "broker", "DISCONNECTED", "MT5_DISCONNECTED; BRIDGE_STOPPED", at)
                store.save()
        finally:
            self.client.shutdown()
            self.attached = False
            self.state = ConnectionState.DISCONNECTED
