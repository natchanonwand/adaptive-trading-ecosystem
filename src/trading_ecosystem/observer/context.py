"""Closed-bar context only; availability and clock time are explicit evidence."""

from datetime import datetime, timedelta

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number, timestamp
from trading_ecosystem.observer.contracts import content_id

TIMEFRAMES = {
    "M1": (1, 60),
    "M5": (5, 300),
    "M15": (15, 900),
    "M30": (30, 1800),
    "H1": (16385, 3600),
    "H4": (16388, 14400),
}


def context_key(symbol: str, at: datetime) -> str:
    return symbol + "@" + at.isoformat()


def build_context(
    symbol: str, at: datetime, quote: Record | None, bars: dict[str, tuple[Record, ...]], count: int
) -> tuple[Record, dict[str, Record]]:
    windows: dict[str, Record] = {}
    refs: Record = {}
    for name, (_, seconds) in TIMEFRAMES.items():
        selected = []
        seen = set()
        for row in sorted(bars.get(name, ()), key=lambda r: number(r["time"])):
            opened = timestamp(row["time"])
            if opened + timedelta(seconds=seconds) > at:
                continue
            if opened in seen:
                raise ValueError("DUPLICATE_CONTEXT_BAR")
            seen.add(opened)
            o, h, low, c = (number(row[k]) for k in ("open", "high", "low", "close"))
            if low <= 0 or low > min(o, c) or h < max(o, c) or low > h:
                raise ValueError("INVALID_CONTEXT_OHLC")
            selected.append(row)
        window: Record = {
            "symbol": symbol,
            "timeframe": name,
            "duration_seconds": seconds,
            "bars": selected[-count:],
            "price_basis": "MT5_CHART_BAR_BASIS_UNVERIFIED",
            "availability_basis": "MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH",
        }
        key = content_id(window)
        windows[key] = window
        refs[name] = {
            "window_id": key,
            "bar_count": len(window["bars"]),
            "status": "AVAILABLE" if len(window["bars"]) >= count else "PARTIAL",
        }
    observed_quote = None
    if quote:
        qt = timestamp(quote["time"], quote.get("time_msc"))
        if qt <= at and at - qt <= timedelta(seconds=5):
            with arithmetic_context():
                bid, ask = number(quote["bid"]), number(quote["ask"])
                if bid <= 0 or ask < bid:
                    raise ValueError("INVALID_OBSERVER_QUOTE")
                observed_quote = {
                    "bid": str(bid),
                    "ask": str(ask),
                    "spread": str(ask - bid),
                    "timestamp": qt.isoformat(),
                }
    return {
        "symbol": symbol,
        "as_of": at.isoformat(),
        "quote": observed_quote,
        "quote_status": "DIRECT" if observed_quote else "UNAVAILABLE_AT_EVENT_TIME",
        "windows": refs,
        "utc_time_of_day": at.time().isoformat(),
        "utc_day_of_week": at.weekday(),
        "session_label": "UNKNOWN",
        "qualification_eligible": False,
    }, windows
