"""Realized-only curves, drawdown spells, periods and descriptive R accounting."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_ecosystem.backtests.metrics import mean, median
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.portfolios.contracts import ASSET_ORDER, ZERO, Episode, Interval
from trading_ecosystem.portfolios.events import concurrency, events, microseconds


def drawdown(
    points: list[tuple[datetime, Decimal]], start: datetime, end: datetime, initial: Decimal = ZERO
) -> dict[str, Any]:
    peak = initial
    peak_time, peak_index = start, 0
    deepest = ZERO
    percent = ZERO
    trough_time: datetime | None = None
    active = False
    trough_value = initial
    spells: list[dict[str, Any]] = []
    for index, (time, value) in enumerate(points, 1):
        difference = value - peak
        deepest = min(deepest, difference)
        if peak > 0:
            percent = min(percent, difference / peak)
        if value < peak:
            active = True
            if trough_time is None or value < trough_value:
                trough_time, trough_value = time, value
        else:
            if active:
                spells.append(
                    {
                        "peak_time": peak_time,
                        "trough_time": trough_time,
                        "recovery_time": time,
                        "recovered": True,
                        "event_duration": index - peak_index,
                        "clock_microseconds": microseconds(time - peak_time),
                        "trough_to_recovery_microseconds": microseconds(time - trough_time)
                        if trough_time
                        else None,
                    }
                )
            active, trough_time = False, None
            peak, peak_time, peak_index = value, time, index
    if active:
        spells.append(
            {
                "peak_time": peak_time,
                "trough_time": trough_time,
                "recovery_time": None,
                "recovered": False,
                "event_duration": len(points) - peak_index,
                "clock_microseconds": microseconds(end - peak_time),
                "trough_to_recovery_microseconds": None,
            }
        )
    return {
        "maximum_drawdown": deepest,
        "maximum_drawdown_fraction": percent,
        "peak": peak,
        "final": points[-1][1] if points else initial,
        "spells": spells,
        "maximum_duration_events": max((item["event_duration"] for item in spells), default=0),
        "maximum_duration_microseconds": max(
            (item["clock_microseconds"] for item in spells), default=0
        ),
        "max_recovered_trough_to_peak_microseconds": max(
            (item["trough_to_recovery_microseconds"] for item in spells if item["recovered"]),
            default=None,
        ),
    }


def periods(points: list[tuple[datetime, Decimal]], interval: Interval) -> dict[str, Any]:
    months: dict[str, dict[str, Any]] = {}
    year, month = interval.start.year, interval.start.month
    last = max([interval.end, *(time for time, _ in points)])
    while (year, month) <= (last.year, last.month):
        months[f"{year:04d}-{month:02d}"] = {"total": ZERO, "episodes": 0}
        month += 1
        if month == 13:
            year, month = year + 1, 1
    years: dict[str, dict[str, Any]] = {
        str(y): {"total": ZERO, "episodes": 0} for y in range(interval.start.year, last.year + 1)
    }
    for time, value in points:
        for bucket in (months[time.strftime("%Y-%m")], years[str(time.year)]):
            bucket["total"] += value
            bucket["episodes"] += 1
    return {"monthly": months, "annual": years}


def r_statistics(episodes: tuple[Episode, ...], interval: Interval) -> dict[str, Any]:
    ordered = [event[-1] for event in events(episodes) if event[-2] == "EXIT"]
    values = [item.gross_price_R for item in ordered]
    positive = [value for value in values if value is not None and value > 0]
    negative = [value for value in values if value is not None and value < 0]
    gross = [value for value in values if value is not None]
    total = sum(gross, ZERO)
    positive_total, negative_total = sum(positive, ZERO), -sum(negative, ZERO)
    winning = losing = max_winning = max_losing = 0
    curve, cumulative = [], ZERO
    period_points = []
    for episode in ordered:
        value = episode.gross_price_R
        if value is None or episode.exit_time is None:
            raise ValueError("MISSING_COMPLETED_R")
        cumulative += value
        curve.append((episode.exit_time, cumulative))
        period_points.append((episode.exit_time, value))
        winning = winning + 1 if value > 0 else 0
        losing = losing + 1 if value < 0 else 0
        max_winning, max_losing = max(max_winning, winning), max(max_losing, losing)
    horizon = max([interval.end, *(time for time, _ in curve)])
    return {
        "episodes": len(gross),
        "open_episodes": len(episodes) - len(gross),
        "wins": len(positive),
        "losses": len(negative),
        "break_even": len(gross) - len(positive) - len(negative),
        "win_rate": Decimal(len(positive)) / len(gross) if gross else None,
        "total_gross_R": total,
        "mean_R": mean(gross),
        "median_R": median(gross),
        "average_winning_R": mean(positive),
        "average_losing_R": mean(negative),
        "profit_factor": {
            "state": "FINITE" if negative else "POSITIVE_INFINITY" if positive else "UNDEFINED",
            "value": positive_total / negative_total if negative else None,
        },
        "maximum_winning_streak": max_winning,
        "maximum_losing_streak": max_losing,
        "curve": [{"exit_time": time, "cumulative_R": value} for time, value in curve],
        "drawdown_label": "REALIZED_EPISODE_R_DRAWDOWN",
        "drawdown": drawdown(curve, interval.start, horizon),
        **periods(period_points, interval),
    }


def r_analysis(episodes: tuple[Episode, ...], interval: Interval) -> dict[str, Any]:
    with arithmetic_context():
        result = r_statistics(episodes, interval)
        result["drawdown"].pop("maximum_drawdown_fraction")
        result["concurrency"] = concurrency(episodes, interval)
        result["contributions"] = {}
        for asset in ASSET_ORDER:
            subset = [
                item for item in episodes if item.asset == asset and item.gross_price_R is not None
            ]
            contribution = sum(
                (item.gross_price_R for item in subset if item.gross_price_R is not None), ZERO
            )
            result["contributions"][asset.value] = {
                "episodes": len(subset),
                "R": contribution,
                "percentage_of_positive_total": contribution / result["total_gross_R"] * 100
                if result["total_gross_R"] > 0
                else None,
            }
        result["splits"] = {
            name: r_statistics(
                tuple(item for item in episodes if interval.split(item.signal_time) == name),
                interval,
            )
            for name in ("Development", "Validation", "Locked OOS")
        }
        result["cross_split_episode_count"] = sum(
            item.exit_time is not None
            and interval.split(item.signal_time) != interval.split(item.exit_time)
            for item in episodes
        )
        return result
