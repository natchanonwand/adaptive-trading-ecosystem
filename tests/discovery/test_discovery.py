import ast
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_ecosystem.discovery.candidates import discover_candidates
from trading_ecosystem.discovery.contracts import (
    DemoRequired,
    DiscoveryError,
    DiscoveryPlan,
    Instrument,
    ProbeInterval,
)
from trading_ecosystem.discovery.normalization import source_decimal
from trading_ecosystem.discovery.probes import probe_bars, probe_ticks
from trading_ecosystem.discovery.provider import Mt5ReadOnlyProvider
from trading_ecosystem.discovery.sdk import _fields, _safe
from trading_ecosystem.domain.primitives import Asset

NOW = datetime(2026, 1, 2, tzinfo=UTC)


class FakeSdk:
    def __init__(self, mode: object = 0) -> None:
        self.mode = mode
        self.calls: list[str] = []
        self.quote: Mapping[str, object] = {"time": 1767312000, "bid": 100.0, "ask": 100.1}
        self.bars: Sequence[Mapping[str, object]] | None = []
        self.ticks: Sequence[Mapping[str, object]] | None = []

    def initialize(self) -> bool:
        self.calls.append("initialize")
        return True

    def shutdown(self) -> None:
        self.calls.append("shutdown")

    def account_info(self) -> Mapping[str, object]:
        return {
            "trade_mode": self.mode,
            "company": "Synthetic Broker",
            "server": "Synthetic-Demo",
            "currency": "USD",
        }

    def terminal_info(self) -> Mapping[str, object]:
        return {"connected": True, "maxbars": 10000}

    def symbols_get(self) -> tuple[Mapping[str, object], ...]:
        self.calls.append("symbols_get")
        return ({"name": "BTCUSD", "description": "Bitcoin", "currency_profit": "USD"},)

    def symbol_info(self, symbol: str) -> Mapping[str, object]:
        return {"name": symbol, "point": 0.01, "digits": 2}

    def symbol_info_tick(self, symbol: str) -> Mapping[str, object]:
        return self.quote

    def symbol_select(self, symbol: str, selected: bool) -> bool:
        self.calls.append("symbol_select")
        return selected

    def copy_rates_range(
        self, symbol: str, start: datetime, end: datetime
    ) -> Sequence[Mapping[str, object]] | None:
        self.calls.append("copy_rates_range")
        assert start.tzinfo is UTC and end.tzinfo is UTC
        return self.bars

    def copy_ticks_range(
        self, symbol: str, start: datetime, end: datetime
    ) -> Sequence[Mapping[str, object]] | None:
        self.calls.append("copy_ticks_range")
        assert end - start <= timedelta(hours=1)
        return self.ticks


@pytest.mark.parametrize("mode", [1, 2, None, "0", True, False, 99])
def test_non_demo_hard_fails_before_catalog_or_history(mode: object) -> None:
    sdk = FakeSdk(mode)
    with pytest.raises(DemoRequired), Mt5ReadOnlyProvider(sdk):
        pytest.fail("must abort")
    assert sdk.calls == ["initialize", "shutdown"]


def test_demo_acceptance_identity_allowlist_and_switch_rejection() -> None:
    sdk = FakeSdk()
    with Mt5ReadOnlyProvider(sdk) as provider:
        identity = provider.get_provider_identity()
        assert identity.account_trade_mode == "DEMO"
        assert set(json.loads(identity.model_dump_json())) == {
            "provider",
            "company",
            "server",
            "account_currency",
            "account_trade_mode",
            "retrieved_at",
            "terminal_maxbars",
            "terminal_connected",
        }
        sdk.mode = 2
        with pytest.raises(DemoRequired):
            provider.list_instruments()
        assert "symbols_get" not in sdk.calls


def test_native_account_fields_exclude_private_values() -> None:
    # No account identifiers or credentials are fixtures: these fields contain
    # opaque sentinels and must not even be extracted from a native record.
    private = object()
    row = SimpleNamespace(
        company="Synthetic",
        server="Demo",
        currency="USD",
        trade_mode=0,
        login=private,
        name=private,
        password=private,
    )
    fields = _fields(row, ("company", "server", "currency", "trade_mode"))
    assert fields is not None and private not in fields.values()
    assert not {"login", "name", "password"} & fields.keys()


def test_native_errors_do_not_leak_credentials() -> None:
    marker = "synthetic-" + "private-marker"

    def fail() -> None:
        raise ValueError(marker)

    with pytest.raises(DiscoveryError) as error:
        _safe(fail)
    assert marker not in str(error.value)
    assert error.value.__context__ is None


def test_candidates_never_auto_approved() -> None:
    instruments = tuple(
        Instrument(
            broker_symbol=name,
            description="Nasdaq 100",
            path="Indices",
            currency_base="USD",
            currency_profit="USD",
            currency_margin="USD",
        )
        for name in ("USTEC100", "NAS100")
    )
    result = discover_candidates(instruments)
    assert len(result) == 2
    assert all(candidate.status == "BLOCKED" for candidate in result)
    assert all(candidate.reason == "AMBIGUOUS_OWNER_APPROVAL_REQUIRED" for candidate in result)
    assert {asset.value for asset in Asset} == {"BTCUSD", "XAUUSD", "USTEC100"}


def test_decimal_normalization_and_missing_metadata() -> None:
    assert source_decimal(0.1) == Decimal("0.1")
    assert source_decimal(float("nan")) is None
    assert source_decimal(True) is None
    with Mt5ReadOnlyProvider(FakeSdk()) as provider:
        metadata = provider.get_instrument_metadata("BTCUSD")
        assert next(field.value for field in metadata.numeric if field.field == "point") == Decimal(
            ".01"
        )
        assert "trade_contract_size" in metadata.missing_or_invalid_fields


@pytest.mark.parametrize("bid,ask", [(0, 1), (-1, 1), (None, 1), (1, float("inf"))])
def test_malformed_quote_rejected(bid: object, ask: object) -> None:
    sdk = FakeSdk()
    sdk.quote = {"time": 1767312000, "bid": bid, "ask": ask}
    with (
        Mt5ReadOnlyProvider(sdk) as provider,
        pytest.raises(DiscoveryError, match="MALFORMED_QUOTE"),
    ):
        provider.get_latest_quote("BTCUSD")


def test_crossed_quote_flag_and_millisecond_time() -> None:
    sdk = FakeSdk()
    sdk.quote = {"time_msc": 1767312000123, "bid": 101.0, "ask": 100.0}
    with Mt5ReadOnlyProvider(sdk) as provider:
        quote = provider.get_latest_quote("BTCUSD")
        assert quote.crossed
        assert quote.time.tzinfo is UTC and quote.time.microsecond == 123000


def test_empty_history_is_explicit_and_naive_input_rejected() -> None:
    interval = ProbeInterval(
        label="test", requested_start=NOW, requested_end=NOW + timedelta(hours=1)
    )
    with Mt5ReadOnlyProvider(FakeSdk()) as provider:
        bars = probe_bars(provider, "BTCUSD", interval)
        ticks = probe_ticks(provider, "BTCUSD", interval, 10)
        assert bars.status == ticks.status == "EMPTY"
        assert ticks.bid_present is None and ticks.first_available_tick is None
        assert ticks.continuous_coverage_established is False
        with pytest.raises(ValueError):
            provider.get_bars("BTCUSD", datetime(2026, 1, 1), NOW)
        with pytest.raises(DiscoveryError):
            provider.get_ticks("BTCUSD", NOW, NOW + timedelta(days=1))


def test_duplicate_and_invalid_ohlc_observations() -> None:
    sdk = FakeSdk()
    row = {"time": int(NOW.timestamp()), "open": 10, "high": 12, "low": 9, "close": 11}
    sdk.bars = [row, row, {**row, "high": 8}]
    interval = ProbeInterval(
        label="test", requested_start=NOW, requested_end=NOW + timedelta(hours=1)
    )
    with Mt5ReadOnlyProvider(sdk) as provider:
        result = probe_bars(provider, "BTCUSD", interval)
        assert (result.row_count, result.duplicate_count, result.invalid_OHLC_count) == (3, 2, 1)
        assert result.calendar_qualified is False


def test_tick_statistics_and_budget_do_not_claim_continuity() -> None:
    sdk = FakeSdk()
    row = {"time_msc": int(NOW.timestamp()) * 1000, "bid": 100, "ask": 101}
    sdk.ticks = [row, row, {**row, "bid": 102}]
    interval = ProbeInterval(
        label="test", requested_start=NOW, requested_end=NOW + timedelta(hours=1)
    )
    with Mt5ReadOnlyProvider(sdk) as provider:
        full = probe_ticks(provider, "BTCUSD", interval, 10)
        limited = probe_ticks(provider, "BTCUSD", interval, 2)
        assert full.duplicate_timestamp_count == 2 and full.crossed_quote_count == 1
        assert full.source_sequence_information == "UNAVAILABLE"
        assert full.continuous_coverage_established is False
        assert limited.status == "BUDGET_LIMIT" and limited.tick_count == 2
        assert limited.requested_interval_fully_queried is False
        assert DiscoveryPlan(as_of=NOW).max_ticks_per_probe == 100000


def test_forbidden_capabilities_absent_and_sdk_calls_allowlisted() -> None:
    forbidden = {"order_send", "order_check", "TradeRequest", "positions_get", "orders_get"}
    allowed = {
        "initialize",
        "shutdown",
        "account_info",
        "terminal_info",
        "symbols_get",
        "symbol_info",
        "symbol_info_tick",
        "symbol_select",
        "copy_rates_range",
        "copy_ticks_range",
        "TIMEFRAME_H1",
        "COPY_TICKS_INFO",
    }
    for path in Path("src/trading_ecosystem/discovery").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(name in source for name in forbidden)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "_mt5"
            ):
                assert node.attr in allowed
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                assert not any(
                    name.split(".")[0] in {"requests", "fastapi", "sklearn", "torch"}
                    for name in names
                )
    assert not any(
        Path("src/trading_ecosystem", name).exists()
        for name in ("strategy", "backtest", "execution", "indicators")
    )


@pytest.mark.parametrize("mode,exit_code", [(0, 0), (2, 2)])
def test_cli_sanitized_outputs_and_real_abort(
    mode: int, exit_code: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from trading_ecosystem.discovery import __main__ as cli

    sdk = FakeSdk(mode)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "NativeSdk", lambda: sdk)
    monkeypatch.setattr("sys.argv", ["discovery", "--catalog-only"])
    assert cli.main() == exit_code
    for path in (tmp_path / "data/discovery").glob("*.json"):
        document = json.loads(path.read_text())

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value))
            return set()

        assert not {"login", "password", "name", "account_id"} & keys(document)
        if exit_code:
            assert document["status"] == "BLOCKED" and document["data"] == []
    if exit_code:
        assert sdk.calls == ["initialize", "shutdown"]


def test_empty_long_tick_probe_has_request_budget() -> None:
    sdk = FakeSdk()
    interval = ProbeInterval(
        label="test", requested_start=NOW, requested_end=NOW + timedelta(days=7)
    )
    with Mt5ReadOnlyProvider(sdk) as provider:
        result = probe_ticks(provider, "BTCUSD", interval, 100000)
    assert result.status == "BUDGET_LIMIT" and result.query_count == 48
    assert result.tick_count == 0 and result.requested_interval_fully_queried is False
