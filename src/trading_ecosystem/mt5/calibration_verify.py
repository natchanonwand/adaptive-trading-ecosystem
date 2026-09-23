"""Reload recorded calculator answers and independently replay the frozen domain."""

from decimal import Decimal
from typing import Any

from trading_ecosystem.mt5.calculations import Side
from trading_ecosystem.mt5.calibration_matrix import calibrate_symbol
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.economics import BrokerInstrumentSnapshot
from trading_ecosystem.mt5.normalization import number


class RecordedCalculator:
    def __init__(self, result: Record) -> None:
        self.profits: dict[tuple[str, Decimal, Decimal, Decimal], Decimal] = {}
        self.margins: dict[tuple[str, Decimal, Decimal], Decimal] = {}
        self.symbol: str = result["broker_symbol"]
        for row in result["profit_rows"]:
            self._profit(
                row["side"],
                row["volume"],
                row["price_open"],
                row["price_close"],
                row["broker_calculated_pnl"],
            )
        for row in result["margin_rows"]:
            self._margin(
                row["side"], row["volume"], row["price"], row["broker_incremental_margin_estimate"]
            )
        for row in result["risk_rows"]:
            self._profit(
                row["side"],
                result["metadata"]["volume_min"],
                row["entry"],
                row["stop"],
                str(-number(row["minimum_lot_broker_loss"])),
            )
            if row["accepted"]:
                self._profit(
                    row["side"],
                    row["selected_volume"],
                    row["entry"],
                    row["stop"],
                    str(-number(row["broker_loss"])),
                )
                self._margin(
                    row["side"],
                    row["selected_volume"],
                    row["entry"],
                    row["broker_incremental_margin_estimate"],
                )

    def _profit(self, side: str, volume: str, opened: str, closed: str, value: str) -> None:
        key = side, number(volume), number(opened), number(closed)
        if key in self.profits and self.profits[key] != number(value):
            raise ValueError("INCONSISTENT_RECORDED_PROFIT")
        self.profits[key] = number(value)

    def _margin(self, side: str, volume: str, price: str, value: str) -> None:
        key = side, number(volume), number(price)
        if key in self.margins and self.margins[key] != number(value):
            raise ValueError("INCONSISTENT_RECORDED_MARGIN")
        self.margins[key] = number(value)

    def profit(
        self, side: Side, symbol: str, volume: Decimal, opened: Decimal, closed: Decimal
    ) -> Decimal:
        if symbol != self.symbol:
            raise ValueError("RECORDED_SYMBOL_MISMATCH")
        return self.profits[side, volume, opened, closed]

    def margin(self, side: Side, symbol: str, volume: Decimal, price: Decimal) -> Decimal:
        if symbol != self.symbol:
            raise ValueError("RECORDED_SYMBOL_MISMATCH")
        return self.margins[side, volume, price]


def verify_report(report: Record) -> None:
    if report["account_kind"] != "DEMO" or report["account_currency"] != "USD":
        raise ValueError("DEMO_USD_EVIDENCE_REQUIRED")
    symbols = report["symbols"]
    if len(symbols) != 3 or {s["logical_symbol"] for s in symbols} != {
        "BTCUSD",
        "XAUUSD",
        "USTEC100",
    }:
        raise ValueError("INCOMPLETE_CALIBRATION_ASSET_MATRIX")
    if report["qualification_eligible"] or report["risk_sizing_ready"]:
        raise ValueError("UNSUPPORTED_QUALIFICATION_CLAIM")
    for symbol in symbols:
        snapshot = BrokerInstrumentSnapshot.model_validate(symbol["evidence"]["snapshot"])
        replay = calibrate_symbol(
            RecordedCalculator(symbol),
            snapshot,
            symbol["quote"],
            report["currency_digits"],
            number(report["observed_account_free_margin"]),
        )
        for key, value in replay.items():
            if value != symbol[key]:
                raise ValueError(f"CALIBRATION_REPLAY_MISMATCH_{key}")
        if symbol["risk_sizing_ready"] or symbol["qualification_eligible"]:
            raise ValueError("UNSUPPORTED_SYMBOL_QUALIFICATION_CLAIM")


def public_report(report: Record) -> Record:
    """Omit internal content identities from the tracked presentation, retain full ignored proof."""

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if key not in {"content_digest", "decision_identity"}
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    result: Record = clean(report)
    result["full_evidence_path"] = ".local/phase4_a1/calibration-20260922-complete.json"
    return result
