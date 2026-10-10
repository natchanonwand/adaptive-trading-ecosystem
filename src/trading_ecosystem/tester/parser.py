"""Deterministic English MT5 HTML report normalization; no OCR or HTML execution."""

import hashlib
import json
import re
from decimal import Decimal, localcontext
from html.parser import HTMLParser
from uuid import UUID

from trading_ecosystem.tester.contracts import Result

NUMERIC = {
    "Initial Deposit": "initial_deposit",
    "Total Net Profit": "net_profit",
    "Gross Profit": "gross_profit",
    "Gross Loss": "gross_loss",
    "Profit Factor": "profit_factor",
    "Expected Payoff": "expected_payoff",
    "Largest profit trade": "largest_profit_trade",
    "Largest loss trade": "largest_loss_trade",
    "Average profit trade": "average_profit_trade",
    "Average loss trade": "average_loss_trade",
}
COUNTS = {
    "Total Trades": "total_trades",
    "Profit Trades (% of total)": "winning_trades",
    "Loss Trades (% of total)": "losing_trades",
    "Long Trades (won %)": "long_trades",
    "Short Trades (won %)": "short_trades",
    "Maximum consecutive wins ($)": "maximum_consecutive_wins",
    "Maximum consecutive losses ($)": "maximum_consecutive_losses",
}
TEXT = {
    "Balance Drawdown Maximal": "balance_drawdown",
    "Equity Drawdown Maximal": "equity_drawdown",
    "Average position holding time": "average_holding_time",
    "Maximal position holding time": "maximum_holding_time",
}
META = {
    "Expert",
    "Symbol",
    "Period",
    "Model",
    "History Quality",
    "Leverage",
    "Currency",
    "Company",
    "Build",
    "Ticks",
}


class Cells(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row:
            self.rows.append(self.row)


def numeric(value: str) -> Decimal:
    # English decimal point only; grouping must be internally consistent.
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,3}(?: \d{3})+)(?:\.\d+)?", value):
        raise ValueError("UNSUPPORTED_NUMERIC_LOCALE")
    return Decimal(value.replace(",", "").replace(" ", ""))


def decode_report(raw: bytes) -> str:
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("REPORT_TOO_LARGE")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def parse(raw: bytes, run_id: UUID, project_id: UUID, candidate_id: UUID) -> Result:
    document = decode_report(raw)
    parser = Cells()
    parser.feed(document)
    known = set(NUMERIC) | set(COUNTS) | set(TEXT) | META
    values: dict[str, str] = {}
    for row in parser.rows:
        for i, cell in enumerate(row[:-1]):
            key = cell.rstrip(":")
            # Native Orders/Deals column headings are not setting/value rows.
            # Colon-labelled duplicate settings still fail closed.
            if cell.endswith(":") and key in known:
                if key in values:
                    raise ValueError("DUPLICATE_REPORT_FIELD")
                values[key] = row[i + 1]
    if not {"Total Net Profit", "Total Trades", "Symbol", "Period", "Expert"} <= values.keys():
        raise ValueError("REQUIRED_REPORT_FIELDS_MISSING")
    metrics: dict[str, str | int | None] = {}
    for label, key in NUMERIC.items():
        metrics[key] = str(numeric(values[label])) if label in values else None
    for label, key in COUNTS.items():
        metrics[key] = None
        if label in values:
            match = re.fullmatch(r"(\d+)(?: \([^()]+\))?", values[label])
            if not match:
                raise ValueError("INVALID_TRADE_COUNT")
            metrics[key] = int(match[1])
    for label, key in TEXT.items():
        value = values.get(label)
        metrics[key] = None
        if value is None:
            continue
        if key.endswith("drawdown"):
            match = re.fullmatch(r"(.+) \((\d+(?:\.\d+)?)%\)", value)
            if not match or not 0 <= numeric(match[2]) <= 100 or numeric(match[1]) < 0:
                raise ValueError("INVALID_DRAWDOWN")
            metrics[key] = f"{numeric(match[1])} ({numeric(match[2])}%)"
        else:
            if not re.fullmatch(r"\d+:[0-5]\d:[0-5]\d", value):
                raise ValueError("INVALID_HOLDING_TIME")
            metrics[key] = value
    metrics["win_rate"] = None
    total, wins, losses = (metrics[k] for k in ("total_trades", "winning_trades", "losing_trades"))
    if isinstance(total, int) and isinstance(wins, int) and isinstance(losses, int):
        if wins + losses != total:
            raise ValueError("INCONSISTENT_TRADE_COUNTS")
        if total:
            with localcontext() as ctx:
                ctx.prec = 28
                metrics["win_rate"] = str(Decimal(wins) / Decimal(total))
    long, short = metrics["long_trades"], metrics["short_trades"]
    if isinstance(long, int) and isinstance(short, int) and long + short != total:
        raise ValueError("INCONSISTENT_DIRECTION_COUNTS")
    metadata = {k: values.get(k, "UNAVAILABLE") for k in sorted(META)}
    period = re.fullmatch(
        r"([A-Z][A-Z0-9]*) \((\d{4}\.\d{2}\.\d{2}) - (\d{4}\.\d{2}\.\d{2})\)", values["Period"]
    )
    if period:
        metadata.update(timeframe=period[1], from_date=period[2], to_date=period[3])
    else:
        metadata.update(timeframe="UNAVAILABLE", from_date="UNAVAILABLE", to_date="UNAVAILABLE")
    body = dict(
        baseline_run_id=str(run_id),
        project_id=str(project_id),
        candidate_id=str(candidate_id),
        metrics=metrics,
        unavailable=sorted(k for k, v in metrics.items() if v is None),
        metadata=metadata,
        report_identity=hashlib.sha256(raw).hexdigest(),
    )
    identity = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return Result.model_validate({**body, "result_identity": identity})
