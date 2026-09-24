"""Causal measurements with per-cell availability and explicit missingness."""

from datetime import datetime, timedelta
from decimal import Decimal

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.indicators import (
    atr,
    ema,
    quantile,
    range_measurements,
    returns,
    rsi,
    std,
)
from trading_ecosystem.features.registry import CATALOG
from trading_ecosystem.features.temporal import temporal
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number, timestamp
from trading_ecosystem.observer.context import TIMEFRAMES
from trading_ecosystem.observer.contracts import Frame
from trading_ecosystem.observer.replay import position_key


def closed_bars(window: Record, cutoff: datetime, timeframe: str) -> list[Record]:
    seconds = TIMEFRAMES[timeframe][1]
    if window.get("timeframe") != timeframe or window.get("duration_seconds") != seconds:
        raise ValueError("TIMEFRAME_CONTRACT_MISMATCH")
    selected = [
        b for b in window["bars"] if timestamp(b["time"]) + timedelta(seconds=seconds) <= cutoff
    ]
    selected.sort(key=lambda b: number(b["time"]))
    if len({b["time"] for b in selected}) != len(selected):
        raise ValueError("DUPLICATE_FEATURE_BAR")
    for b in selected:
        o, h, low, c = (number(b[k]) for k in ("open", "high", "low", "close"))
        if (
            not all(v.is_finite() for v in (o, h, low, c))
            or low <= 0
            or low > min(o, c)
            or h < max(o, c)
        ):
            raise ValueError("INVALID_FEATURE_BAR")
    return selected


def causal_features(
    event: Record,
    frames: tuple[Frame, ...],
    market: dict[str, Record],
    all_events: list[Record],
    config: BuildConfig,
) -> tuple[Record, Record, Record]:
    cutoff = utc_timestamp(event["observed_at"])
    entry_at = utc_timestamp(event["broker_at"]) if event.get("broker_at") else cutoff
    if entry_at > cutoff:
        raise ValueError("ENTRY_AFTER_OBSERVATION")
    values: Record = {d.name: None for d in CATALOG if d.causal}
    available: Record = dict.fromkeys(values)
    reasons: Record = dict.fromkeys(values, "SOURCE_UNAVAILABLE")

    def put(
        name: str, value: object, at: datetime = cutoff, reason: str = "SOURCE_UNAVAILABLE"
    ) -> None:
        if at > cutoff:
            raise ValueError("FEATURE_LEAKAGE")
        if value is not None:
            values[name] = str(value) if isinstance(value, Decimal) else value
            available[name] = at.isoformat()
            reasons.pop(name, None)
        else:
            reasons[name] = reason

    with arithmetic_context():
        for key, value in temporal(entry_at, config).items():
            put(key, value)
        opening = (
            event["kind"] in {"POSITION_OPENED", "POSITION_INCREASED"}
            and event.get("broker_at") is not None
        )
        ev = event["values"]
        price = number(ev["price"]) if opening else None
        volume = number(ev["volume"]) if opening else None
        side = ev.get("direction")
        put("entry_volume", volume, reason="RECOVERED_ENTRY_UNKNOWN")
        put("observation_quality", event["quality"])
        put("source_confidence", event["attribution"]["confidence"])
        put("entry_time_known", opening)
        # Delayed history discovery must not promote its poll's later state to entry state.
        eligible = [
            f
            for f in frames
            if f.observed_at <= entry_at and entry_at - f.observed_at <= timedelta(seconds=5)
        ]
        snapshot = eligible[-1] if eligible else None
        position = (
            next((p for p in snapshot.positions if position_key(p) == event["position_id"]), None)
            if snapshot
            else None
        )
        metadata = snapshot.metadata.get(event["symbol"], {}) if snapshot else {}
        tick = number(metadata["trade_tick_size"]) if metadata.get("trade_tick_size") else None
        point = number(metadata["point"]) if metadata.get("point") else None
        distances: dict[str, Decimal | None] = {"SL": None, "TP": None}
        if position is not None and snapshot is not None:
            for stop, field in (("SL", "sl"), ("TP", "tp")):
                raw = position.get(field)
                put(
                    "has_" + stop,
                    bool(number(raw)) if raw is not None else None,
                    snapshot.observed_at,
                )
                if (
                    raw is not None
                    and number(raw) > 0
                    and price is not None
                    and side in ("BUY", "SELL")
                ):
                    distance = (
                        (price - number(raw))
                        * (1 if side == "BUY" else -1)
                        * (1 if stop == "SL" else -1)
                    )
                    distances[stop] = distance if distance > 0 else None
                put(
                    "initial_" + stop + "_distance",
                    distances[stop],
                    snapshot.observed_at,
                    "MISSING_OR_INVALID_STOP",
                )
                stop_distance = distances[stop]
                put(
                    stop + "_distance_ticks",
                    stop_distance / tick
                    if stop_distance is not None and tick and tick > 0
                    else None,
                    snapshot.observed_at,
                )
            same = [p for p in snapshot.positions if p["symbol"] == event["symbol"]]
            put("same_symbol_open_count", len(same), snapshot.observed_at)
            put(
                "same_symbol_total_volume",
                sum((number(p["volume"]) for p in same), Decimal(0)),
                snapshot.observed_at,
            )
            if side in ("BUY", "SELL"):
                put(
                    "same_direction_open_count",
                    sum(p["type"] == (0 if side == "BUY" else 1) for p in same),
                    snapshot.observed_at,
                )
                put(
                    "opposite_direction_open_count",
                    sum(p["type"] != (0 if side == "BUY" else 1) for p in same),
                    snapshot.observed_at,
                )
        put(
            "reward_to_risk_observed",
            distances["TP"] / distances["SL"] if distances["TP"] and distances["SL"] else None,
        )
        equity = (
            number(snapshot.account["equity"])
            if snapshot and snapshot.account.get("equity") is not None
            else None
        )
        contract = (
            number(metadata["trade_contract_size"]) if metadata.get("trade_contract_size") else None
        )
        notional = (
            price * volume * contract
            if price is not None and volume is not None and contract and contract > 0
            else None
        )
        put("entry_account_equity", equity)
        put("notional_exposure", notional)
        account_currency = snapshot.account.get("currency") if snapshot else None
        profit_currency = metadata.get("currency_profit")
        put(
            "notional_to_equity",
            notional / equity
            if notional is not None
            and equity
            and equity > 0
            and account_currency
            and account_currency == profit_currency
            else None,
            reason="UNKNOWN_OR_MISMATCHED_CURRENCY_OR_EQUITY",
        )
        context = market.get(event.get("context_reference") or "", {})
        if context and utc_timestamp(context["as_of"]) > entry_at:
            raise ValueError("FUTURE_CONTEXT_REFERENCE")
        quote = context.get("quote")
        spread = None
        if quote:
            qt = utc_timestamp(quote["timestamp"])
            if qt > entry_at:
                raise ValueError("FUTURE_ENTRY_QUOTE")
            bid, ask = number(quote["bid"]), number(quote["ask"])
            if bid <= 0 or ask < bid:
                raise ValueError("INVALID_ENTRY_QUOTE")
            spread = ask - bid
            put("entry_spread_absolute", spread, qt)
            put("entry_spread_points", spread / point if point and point > 0 else None, qt)
            put("entry_spread_ticks", spread / tick if tick and tick > 0 else None, qt)
            put("entry_spread_bps", spread / ((bid + ask) / 2) * 10000, qt)
            historical: dict[datetime, Decimal] = {}
            for f in frames:
                if f.observed_at > cutoff:
                    continue
                q = f.quotes.get(event["symbol"])
                if q:
                    at = timestamp(q["time"], q.get("time_msc"))
                    if (
                        at <= entry_at
                        and number(q["bid"]) > 0
                        and number(q["ask"]) >= number(q["bid"])
                    ):
                        historical[at] = number(q["ask"]) - number(q["bid"])
            historical[qt] = spread
            samples = [v for _, v in sorted(historical.items())][-config.recent_quote_count :]
            median = quantile(samples, Decimal(".5"))
            if len(samples) >= 2:
                put(
                    "entry_spread_percentile_recent",
                    Decimal(sum(v <= spread for v in samples)) / len(samples),
                    qt,
                )
                put(
                    "entry_spread_vs_recent_median",
                    spread / median if median and median > 0 else None,
                    qt,
                )
        bars_by_tf: dict[str, list[Record]] = {}
        quality: Record = {}
        for tf in TIMEFRAMES:
            ref = context.get("windows", {}).get(tf)
            window = market.get(ref["window_id"]) if ref else None
            bars = closed_bars(window, entry_at, tf) if window else []
            bars_by_tf[tf] = bars
            quality[tf + "_history_count"] = len(bars)
            quality[tf + "_history_sufficient"] = len(bars) >= max(
                d.lookback or 1 for d in CATALOG if d.timeframe == tf.lower()
            )
            quality[tf + "_gaps"] = sum(
                number(b["time"]) - number(a["time"]) != TIMEFRAMES[tf][1]
                for a, b in zip(bars, bars[1:], strict=False)
            )
        put(
            "market_context_complete",
            bool(context)
            and all(
                context.get("windows", {}).get(tf, {}).get("status") == "AVAILABLE"
                for tf in TIMEFRAMES
            ),
        )
        for tf, bars in bars_by_tf.items():
            closes = [number(b["close"]) for b in bars]
            at = (
                timestamp(bars[-1]["time"]) + timedelta(seconds=TIMEFRAMES[tf][1])
                if bars
                else entry_at
            )
            prefix = tf.lower()
            volatility = atr(bars)
            if tf != "M1":
                put(prefix + "_atr14", volatility, at, "INSUFFICIENT_HISTORY")
            for lag in (1, 3, 5, 10) if tf == "M15" else (1,):
                put(f"{prefix}_return_{lag}", returns(closes, lag), at, "INSUFFICIENT_HISTORY")
            if tf in ("M15", "H1"):
                put(prefix + "_rsi14", rsi(closes), at, "INSUFFICIENT_HISTORY")
            if tf == "H1":
                averages = {n: ema(closes, n) for n in (20, 50, 200)}
                for n, average in averages.items():
                    ema_distance = (
                        price - average if price is not None and average is not None else None
                    )
                    put(f"h1_ema{n}", average, at, "INSUFFICIENT_HISTORY")
                    put(
                        f"h1_ema{n}_distance_atr",
                        ema_distance / volatility
                        if ema_distance is not None and volatility
                        else None,
                        cutoff,
                        "INSUFFICIENT_HISTORY_OR_ENTRY",
                    )
                for a, b in ((20, 50), (50, 200)):
                    short_average, long_average = averages[a], averages[b]
                    put(
                        f"h1_ema{a}_minus_ema{b}",
                        short_average - long_average
                        if short_average is not None and long_average is not None
                        else None,
                        at,
                        "INSUFFICIENT_HISTORY",
                    )
            if tf == "M15":
                for n in (20,):
                    measures = range_measurements(bars, n, price)
                    for key in (
                        "distance_high",
                        "distance_low",
                        "range_position",
                        "bars_since_high",
                        "bars_since_low",
                    ):
                        put(
                            f"m15_{key}_{n}", measures[key], cutoff, "INSUFFICIENT_HISTORY_OR_ENTRY"
                        )
                for n in (10, 20):
                    put(
                        f"m15_range_{n}",
                        range_measurements(bars, n, price)["range"],
                        at,
                        "INSUFFICIENT_HISTORY",
                    )
                history_returns = [
                    closes[i] / closes[i - 1] - 1
                    for i in range(max(1, len(closes) - 20), len(closes))
                ]
                put(
                    "m15_return_std_20",
                    std(history_returns) if len(history_returns) == 20 else None,
                    at,
                    "INSUFFICIENT_HISTORY",
                )
                bar_range = number(bars[-1]["high"]) - number(bars[-1]["low"]) if bars else None
                put("m15_bar_range", bar_range, at, "INSUFFICIENT_HISTORY")
                for key, value in (
                    ("stop_distance", distances["SL"]),
                    ("tp_distance", distances["TP"]),
                    ("spread", spread),
                    ("bar_range", bar_range),
                ):
                    put(
                        "m15_" + key + "_atr",
                        value / volatility if value is not None and volatility else None,
                    )
        attribution = event["attribution"]
        known = (
            attribution.get("source") == "EXTERNAL_EA" and attribution.get("confidence") == "KNOWN"
        )
        if known and opening:
            prior = sorted(
                [
                    e
                    for e in all_events
                    if e["kind"] == "POSITION_OPENED"
                    and e["event_id"] != event["event_id"]
                    and e["symbol"] == event["symbol"]
                    and e["attribution"] == attribution
                    and e.get("broker_at")
                    and utc_timestamp(e["broker_at"]) < entry_at
                    and utc_timestamp(e["observed_at"]) <= cutoff
                ],
                key=lambda e: (e["broker_at"], e["event_id"]),
            )
            if prior:
                previous = prior[-1]
                p = previous["values"]
                put("previous_episode_direction", p["direction"])
                put(
                    "time_since_previous_entry",
                    Decimal(str((entry_at - utc_timestamp(previous["broker_at"])).total_seconds())),
                )
                put("previous_entry_volume", number(p["volume"]))
                put(
                    "volume_ratio_vs_previous",
                    volume / number(p["volume"])
                    if volume is not None and number(p["volume"]) > 0
                    else None,
                )
                put(
                    "price_distance_from_previous_entry",
                    price - number(p["price"]) if price is not None else None,
                )
            length = 1
            for previous in reversed(prior):
                if previous["values"]["direction"] != side:
                    break
                length += 1
            put("same_direction_sequence_length", length)
            closed = [
                e
                for e in all_events
                if e["kind"] == "POSITION_CLOSED"
                and e["symbol"] == event["symbol"]
                and e["attribution"] == attribution
                and e.get("broker_at")
                and utc_timestamp(e["broker_at"]) < entry_at
                and utc_timestamp(e["observed_at"]) <= cutoff
            ]
            if closed:
                put(
                    "time_since_previous_exit",
                    Decimal(
                        str(
                            (
                                entry_at - max(utc_timestamp(e["broker_at"]) for e in closed)
                            ).total_seconds()
                        )
                    ),
                )
        quality.update(
            account_currency=account_currency,
            profit_currency=profit_currency,
            missing=reasons,
            recovered_episode=not opening or event["recovered_state"],
            ambiguous_attribution=not known,
            initial_state_basis="SNAPSHOT_AT_OR_BEFORE_BROKER_ENTRY_MAX_5_SECONDS",
        )
    return values, available, quality
