"""Bounded polling, transactional restart and event-triggered market windows."""

from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import Engine, select, update

from trading_ecosystem.mt5.calibration import require_demo
from trading_ecosystem.mt5.client import Mt5ReadClient, Record
from trading_ecosystem.mt5.normalization import account_identity, normalize, timestamp
from trading_ecosystem.observer.context import TIMEFRAMES, build_context, context_key
from trading_ecosystem.observer.contracts import Frame, ObservationSession, content_id
from trading_ecosystem.observer.store import append, load_frames, register, sessions


class ObserverClient(Mt5ReadClient, Protocol):
    def bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> tuple[Record, ...]: ...


def stable_positions(rows: tuple[Record, ...]) -> tuple[Record, ...]:
    # Quotes and floating P/L change without a behavioral action. They belong in context.
    ignored = {"price_current", "profit", "swap", "time_update", "time_update_msc"}
    return tuple(
        {k: v for k, v in r.items() if k not in ignored}
        for r in sorted(rows, key=lambda r: int(r["ticket"]))
    )


class Observer:
    def __init__(self, client: ObserverClient, engine: Engine, session: ObservationSession) -> None:
        self.client, self.engine, self.session = client, engine, session
        with engine.begin() as conn:
            register(conn, session)
            retained = load_frames(conn, session)
        self.previous = retained[-1] if retained else None
        self.seen = {str(d["ticket"]): d for f in retained for d in f.deals}
        self.seen_history_orders = {str(o["ticket"]): o for f in retained for o in f.history_orders}
        self.recovered = bool(retained)
        self.last_history: datetime | None = None
        self.history_cursor = (
            self.previous.observed_at
            if self.previous
            else session.started_at - timedelta(days=session.config.history_days)
        )
        self.polls = self.failures = self.new_frames = 0

    def heartbeat(self, at: datetime, status: str, **values: object) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(sessions)
                .where(sessions.c.session_id == self.session.session_id)
                .values(
                    status=status,
                    heartbeat={
                        "at": at.isoformat(),
                        "polls": self.polls,
                        "failures": self.failures,
                        "new_frames": self.new_frames,
                        **values,
                    },
                )
            )

    def step(self, at: datetime | None = None) -> bool:
        at = at or datetime.now(UTC)
        self.polls += 1
        try:
            self._step(at)
            self.heartbeat(at, "OBSERVING")
            return True
        except Exception:
            self.failures += 1
            self.recovered = True
            self.heartbeat(at, "DEGRADED", reason="OBSERVATION_FAILED_NO_NEW_STATE_ACCEPTED")
            return False

    def _step(self, at: datetime) -> None:
        account, terminal = self.client.account_info(), self.client.terminal_info()
        require_demo(account, terminal)
        if account_identity(account) != self.session.account_scope:
            raise ValueError("OBSERVER_ACCOUNT_CHANGED")
        if account.get("margin_mode") != self.session.margin_mode:
            raise ValueError("OBSERVER_POSITION_MODE_CHANGED")
        config = self.session.config
        positions = tuple(
            normalize(r) for r in self.client.positions_get() if r["symbol"] in config.symbols
        )
        orders = tuple(
            normalize(r) for r in self.client.orders_get() if r["symbol"] in config.symbols
        )
        deals: tuple[Record, ...] = ()
        history_orders: tuple[Record, ...] = ()
        history_due = (
            self.last_history is None
            or (at - self.last_history).total_seconds() >= config.history_seconds
        )
        if history_due:
            start = self.history_cursor - timedelta(seconds=config.overlap_seconds)
            raw_deals = self.client.history_deals_get(start, at)
            raw_orders = self.client.history_orders_get(start, at)
            if max(len(raw_deals), len(raw_orders)) > config.max_records:
                raise ValueError("OBSERVER_HISTORY_LIMIT")
            selected = [normalize(r) for r in raw_deals if r.get("symbol") in config.symbols]
            for row in selected:
                old = self.seen.get(str(row["ticket"]))
                if old is not None and old != row:
                    raise ValueError("CONFLICTING_DEAL_REVISION")
            deals = tuple(r for r in selected if str(r["ticket"]) not in self.seen)
            history_orders = tuple(
                normalize(r)
                for r in raw_orders
                if r.get("symbol") in config.symbols
                and self.seen_history_orders.get(str(r["ticket"])) != normalize(r)
            )
        changed = self.previous is None or (
            stable_positions(positions) != stable_positions(self.previous.positions)
            or stable_positions(orders) != stable_positions(self.previous.orders)
        )
        if not changed and not deals and not history_orders:
            if history_due:
                self.last_history, self.history_cursor = at, at
            return
        quotes = {s: normalize(self.client.symbol_info_tick(s)) for s in config.symbols}
        metadata = {s: normalize(self.client.symbol_info(s)) for s in config.symbols}
        cutoffs = {(s, at) for s in config.symbols}
        cutoffs.update((str(d["symbol"]), timestamp(d["time"], d.get("time_msc"))) for d in deals)
        contexts: dict[str, Record] = {}
        all_windows: dict[str, Record] = {}
        for symbol in config.symbols:
            first = min(t for s, t in cutoffs if s == symbol)
            bars: dict[str, tuple[Record, ...]] = {}
            for timeframe, (_, seconds) in TIMEFRAMES.items():
                try:
                    bars[timeframe] = self.client.bars(
                        symbol,
                        timeframe,
                        first - timedelta(seconds=seconds * config.bars_per_window * 3),
                        at,
                    )
                except Exception:
                    # Explicit PARTIAL context, never substituted future or synthetic bars.
                    bars[timeframe] = ()
            for _, cutoff in sorted((s, t) for s, t in cutoffs if s == symbol):
                context, windows = build_context(
                    symbol, cutoff, quotes[symbol], bars, config.bars_per_window
                )
                contexts[context_key(symbol, cutoff)] = context
                all_windows.update(windows)
        frame = Frame(
            session_id=self.session.session_id,
            sequence=self.previous.sequence + 1 if self.previous else 1,
            observed_at=at,
            recovered=self.recovered,
            account=normalize(account),
            positions=positions,
            orders=orders,
            deals=deals,
            history_orders=history_orders,
            quotes=quotes,
            metadata=metadata,
            contexts=contexts,
        )
        with self.engine.begin() as conn:
            # Lock verifies another observer did not advance this session concurrently.
            conn.execute(
                select(sessions.c.session_id)
                .where(sessions.c.session_id == self.session.session_id)
                .with_for_update()
            ).one()
            append(conn, self.session, frame, all_windows)
        self.previous = frame
        self.seen.update({str(r["ticket"]): r for r in deals})
        self.seen_history_orders.update({str(r["ticket"]): r for r in history_orders})
        if history_due:
            self.last_history, self.history_cursor = at, at
        self.new_frames += 1
        self.recovered = False

    def stop(self, at: datetime) -> None:
        self.heartbeat(at, "STOPPED", ended_at=at.isoformat())

    @property
    def config_hash(self) -> str:
        return content_id(self.session.config.model_dump(mode="json"))
