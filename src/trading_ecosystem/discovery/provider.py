"""DEMO-gated read-only provider. Native errors and account records never escape."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from trading_ecosystem.discovery.contracts import (
    AccountEnvironment,
    BarBatch,
    BarCoverage,
    BarObservation,
    DemoRequired,
    DiscoveryError,
    DiscoveryPlan,
    Instrument,
    InstrumentMetadata,
    IntegerMetadata,
    NumericMetadata,
    ProviderIdentity,
    QuoteObservation,
    TickBatch,
    TickCoverage,
    TickObservation,
)
from trading_ecosystem.discovery.normalization import (
    DECIMAL_FIELDS,
    INTEGER_FIELDS,
    TEXT_FIELDS,
    instrument,
    safe_text,
    source_decimal,
    source_integer,
    source_time,
)
from trading_ecosystem.discovery.sdk import DiscoverySdk
from trading_ecosystem.domain.primitives import utc_timestamp


class Mt5ReadOnlyProvider:
    def __init__(self, sdk: DiscoverySdk) -> None:
        self._sdk = sdk
        self._ready = False

    def __enter__(self) -> "Mt5ReadOnlyProvider":
        try:
            if not self._sdk.initialize():
                raise DiscoveryError("TERMINAL_INITIALIZATION_FAILED")
            self._ready = True
            self.get_account_environment()
            return self
        except Exception:
            self._ready = False
            self._sdk.shutdown()
            raise

    def __exit__(self, *args: object) -> None:
        self._ready = False
        self._sdk.shutdown()

    def get_account_environment(self) -> AccountEnvironment:
        if not self._ready:
            raise DemoRequired("DEMO_NOT_CONFIRMED")
        account = self._sdk.account_info()
        # MT5's documented account mode enum: DEMO=0. Reject missing, bool,
        # text, REAL and CONTEST; a server name containing 'demo' is not evidence.
        if account is None or source_integer(account.get("trade_mode")) != 0:
            self._ready = False
            raise DemoRequired("CONNECTED_ACCOUNT_NOT_CONFIRMED_DEMO")
        terminal = self._sdk.terminal_info()
        if terminal is None or terminal.get("connected") is not True:
            raise DemoRequired("TERMINAL_NOT_CONNECTED")
        return AccountEnvironment(retrieved_at=datetime.now(UTC))

    def get_provider_identity(self) -> ProviderIdentity:
        self.get_account_environment()
        account = self._sdk.account_info()
        terminal = self._sdk.terminal_info()
        if account is None or source_integer(account.get("trade_mode")) != 0:
            raise DemoRequired("CONNECTED_ACCOUNT_NOT_CONFIRMED_DEMO")
        if terminal is None or terminal.get("connected") is not True:
            raise DemoRequired("TERMINAL_NOT_CONNECTED")
        return ProviderIdentity(
            company=safe_text(account.get("company")),
            server=safe_text(account.get("server")),
            account_currency=safe_text(account.get("currency")),
            retrieved_at=datetime.now(UTC),
            terminal_maxbars=source_integer(terminal.get("maxbars")),
            terminal_connected=True,
        )

    def list_instruments(self) -> tuple[Instrument, ...]:
        self.get_account_environment()
        rows = self._sdk.symbols_get()
        self.get_account_environment()
        try:
            return tuple(instrument(row) for row in rows)
        except ValueError:
            raise DiscoveryError("INVALID_SYMBOL_CATALOG") from None

    def _select(self, symbol: str) -> None:
        self.get_account_environment()
        if not self._sdk.symbol_select(symbol, True):
            raise DiscoveryError("SYMBOL_SELECTION_FAILED")
        self.get_account_environment()

    def get_instrument_metadata(self, symbol: str) -> InstrumentMetadata:
        self._select(symbol)
        row = self._sdk.symbol_info(symbol)
        self.get_account_environment()
        if row is None:
            raise DiscoveryError("METADATA_UNAVAILABLE")
        base = instrument(row)
        numeric = tuple(
            NumericMetadata(field=name, value=source_decimal(row.get(name)))
            for name in DECIMAL_FIELDS
        )
        integer = tuple(
            IntegerMetadata(field=name, value=source_integer(row.get(name)))
            for name in INTEGER_FIELDS
        )
        missing = [field.field for field in numeric if field.value is None]
        missing.extend(field.field for field in integer if field.value is None)
        missing.extend(name for name in TEXT_FIELDS if safe_text(row.get(name)) is None)
        return InstrumentMetadata(
            **base.model_dump(),
            retrieved_at=datetime.now(UTC),
            numeric=numeric,
            integer=integer,
            missing_or_invalid_fields=tuple(missing),
        )

    def get_latest_quote(self, symbol: str) -> QuoteObservation:
        self._select(symbol)
        row = self._sdk.symbol_info_tick(symbol)
        self.get_account_environment()
        if row is None:
            raise DiscoveryError("QUOTE_UNAVAILABLE")
        try:
            time, milliseconds = source_time(row)
            return QuoteObservation.model_validate(
                {
                    "broker_symbol": symbol,
                    "time": time,
                    "retrieved_at": datetime.now(UTC),
                    "bid": source_decimal(row.get("bid")),
                    "ask": source_decimal(row.get("ask")),
                    "time_precision": "MILLISECOND" if milliseconds else "SECOND",
                }
            )
        except (ValueError, OverflowError, ValidationError):
            raise DiscoveryError("MALFORMED_QUOTE") from None

    @staticmethod
    def _interval(start: datetime, end: datetime, maximum: timedelta) -> tuple[datetime, datetime]:
        start, end = utc_timestamp(start), utc_timestamp(end)
        if not timedelta(0) < end - start <= maximum:
            raise DiscoveryError("PROBE_INTERVAL_OUTSIDE_BOUND")
        return start, end

    def get_bars(self, symbol: str, start: datetime, end: datetime) -> BarBatch:
        start, end = self._interval(start, end, timedelta(days=366))
        self._select(symbol)
        raw = self._sdk.copy_rates_range(symbol, start, end - timedelta(milliseconds=1))
        self.get_account_environment()
        if raw is None:
            return BarBatch(rows=(), error="SDK_EMPTY_OR_UNAVAILABLE")
        rows = []
        malformed = 0
        for row in raw:
            try:
                time, _ = source_time(row)
            except (ValueError, OverflowError):
                malformed += 1
                continue
            if start <= time < end:
                rows.append(
                    BarObservation(
                        time=time,
                        open=source_decimal(row.get("open")),
                        high=source_decimal(row.get("high")),
                        low=source_decimal(row.get("low")),
                        close=source_decimal(row.get("close")),
                    )
                )
        return BarBatch(rows=tuple(rows), malformed_time_count=malformed)

    def get_ticks(self, symbol: str, start: datetime, end: datetime) -> TickBatch:
        start, end = self._interval(start, end, timedelta(hours=1))
        self._select(symbol)
        raw = self._sdk.copy_ticks_range(symbol, start, end - timedelta(milliseconds=1))
        self.get_account_environment()
        if raw is None:
            return TickBatch(rows=(), error="SDK_EMPTY_OR_UNAVAILABLE")
        rows = []
        malformed = 0
        for row in raw[:100_000]:
            try:
                time, milliseconds = source_time(row)
            except (ValueError, OverflowError):
                malformed += 1
                continue
            if start <= time < end:
                rows.append(
                    TickObservation(
                        time=time,
                        bid=source_decimal(row.get("bid")),
                        ask=source_decimal(row.get("ask")),
                        time_precision="MILLISECOND" if milliseconds else "SECOND",
                    )
                )
        return TickBatch(
            rows=tuple(rows), malformed_time_count=malformed, truncated=len(raw) > 100_000
        )

    def probe_history_coverage(
        self, symbol: str, plan: DiscoveryPlan
    ) -> Iterator[BarCoverage | TickCoverage]:
        from trading_ecosystem.discovery.probes import probe_symbol

        yield from probe_symbol(self, symbol, plan)
