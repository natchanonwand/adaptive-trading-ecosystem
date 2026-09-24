"""Small, explicit feature catalog. Changes to these definitions change feature-set identity."""

import hashlib
from pathlib import Path

from trading_ecosystem.features.contracts import Definition
from trading_ecosystem.observer.contracts import content_id


def catalog() -> tuple[Definition, ...]:
    rows: list[Definition] = []

    def add(
        name: str,
        family: str,
        definition: str,
        *,
        dtype: str = "decimal",
        source: str = "ENTRY_OBSERVATION",
        lookback: int | None = None,
        timeframe: str | None = None,
        causal: bool = True,
    ) -> None:
        rows.append(
            Definition.model_validate(
                dict(
                    name=name,
                    family=family,
                    dtype=dtype,
                    definition=definition,
                    source=source,
                    lookback=lookback,
                    timeframe=timeframe,
                    availability="SOURCE_AT_OR_BEFORE_ENTRY_CUTOFF"
                    if causal
                    else "POST_ENTRY_OBSERVATION",
                    causal=causal,
                )
            )
        )

    for name, dtype, definition in (
        ("hour_utc", "integer", "UTC hour of broker entry, or first observation when unknown"),
        ("minute_utc", "integer", "UTC minute of entry time basis"),
        ("day_of_week", "integer", "UTC weekday Monday=0"),
        (
            "session",
            "string",
            "Configured fixed UTC windows; overlap joined by +; not civil DST sessions",
        ),
        (
            "minutes_since_session_open",
            "integer",
            "Minutes since sole matching UTC window; overlap null",
        ),
    ):
        add(name, "Temporal", definition, dtype=dtype)
    for tf in ("m5", "m15", "m30", "h1", "h4"):
        add(
            tf + "_atr14",
            "Volatility",
            "Wilder14 TR; seed mean of first14 TR after previous close; finite retained window",
            source="CLOSED_BARS",
            lookback=15,
            timeframe=tf,
        )
    for n in (20, 50, 200):
        for suffix, definition in (
            ("", "SMA-seeded EMA, alpha 2/(period+1), retained closed window"),
            ("_distance_atr", "Entry price minus EMA divided by H1 ATR14"),
        ):
            add(
                f"h1_ema{n}" + suffix,
                "Trend",
                definition,
                source="CLOSED_BARS_AND_ENTRY_PRICE",
                lookback=n,
                timeframe="h1",
            )
    for a, b in ((20, 50), (50, 200)):
        add(
            f"h1_ema{a}_minus_ema{b}",
            "Trend",
            "Difference between two independently seeded EMAs",
            source="CLOSED_BARS",
            lookback=b,
            timeframe="h1",
        )
    for tf in ("m15", "h1"):
        add(
            tf + "_rsi14",
            "Momentum",
            "Wilder14 gains/losses; flat=50, zero loss positive gain=100",
            source="CLOSED_BARS",
            lookback=15,
            timeframe=tf,
        )
    for tf in ("m1", "m5", "m15", "m30", "h1", "h4"):
        for lag in (1, 3, 5, 10) if tf == "m15" else (1,):
            add(
                f"{tf}_return_{lag}",
                "Momentum",
                "Last eligible close / close lag bars earlier minus one",
                source="CLOSED_BARS",
                lookback=lag + 1,
                timeframe=tf,
            )
    for n in (20,):
        for suffix, definition, dtype in (
            ("distance_high", "Recent high minus entry price", "decimal"),
            ("distance_low", "Entry price minus recent low", "decimal"),
            (
                "range_position",
                "(entry-low)/(high-low); flat range null; may exceed [0,1]",
                "decimal",
            ),
            ("bars_since_high", "Bars since most recent equal highest high", "integer"),
            ("bars_since_low", "Bars since most recent equal lowest low", "integer"),
        ):
            add(
                f"m15_{suffix}_{n}",
                "Market Structure",
                definition,
                dtype=dtype,
                source="CLOSED_BARS_AND_ENTRY_PRICE",
                lookback=n,
                timeframe="m15",
            )
    for n in (10, 20):
        add(
            f"m15_range_{n}",
            "Volatility",
            "Maximum high minus minimum low in N closed bars",
            source="CLOSED_BARS",
            lookback=n,
            timeframe="m15",
        )
    add(
        "m15_return_std_20",
        "Volatility",
        "Population standard deviation of 20 simple one-bar returns",
        source="CLOSED_BARS",
        lookback=21,
        timeframe="m15",
    )
    add(
        "m15_bar_range",
        "Volatility",
        "Last eligible closed bar high-low",
        source="CLOSED_BARS",
        lookback=1,
        timeframe="m15",
    )
    for part in ("stop_distance", "tp_distance", "spread", "bar_range"):
        add(
            "m15_" + part + "_atr",
            "Volatility",
            part + " divided by positive M15 ATR14",
            source="CLOSED_BARS_AND_ENTRY_CONTEXT",
            lookback=15,
            timeframe="m15",
        )
    for name, definition in (
        ("entry_spread_absolute", "Contemporaneous observed ask-bid"),
        ("entry_spread_points", "Observed spread / instrument point"),
        ("entry_spread_ticks", "Observed spread / instrument tick size"),
        ("entry_spread_bps", "Observed spread / bid-ask midpoint *10000"),
        (
            "entry_spread_percentile_recent",
            "Fraction of recent distinct eligible quote spreads <= current; at least two quotes",
        ),
        (
            "entry_spread_vs_recent_median",
            "Current spread / median last configured observed spreads; at least2",
        ),
    ):
        add(name, "Execution / Spread", definition, source="OBSERVED_QUOTES_AND_METADATA")
    for name, definition in (
        (
            "initial_SL_distance",
            "Entry price minus BUY SL or SELL SL minus entry; only valid first entry-time snapshot",
        ),
        (
            "initial_TP_distance",
            "BUY TP minus entry or entry minus SELL TP; only valid first entry-time snapshot",
        ),
        ("SL_distance_ticks", "Valid initial SL distance / tick size"),
        ("TP_distance_ticks", "Valid initial TP distance / tick size"),
        ("reward_to_risk_observed", "Valid positive TP distance / valid positive SL distance"),
    ):
        add(name, "Price / Distance", definition, source="ENTRY_TIME_POSITION_AND_METADATA")
    for name, dtype, definition in (
        (
            "entry_volume",
            "decimal",
            "Confirmed entry fill lots; recovered snapshot volume not an entry",
        ),
        (
            "same_symbol_open_count",
            "integer",
            "Positions in latest eligible entry-time snapshot, same symbol",
        ),
        (
            "same_direction_open_count",
            "integer",
            "Same-symbol same-direction positions in eligible snapshot",
        ),
        (
            "opposite_direction_open_count",
            "integer",
            "Same-symbol opposite-direction positions in eligible snapshot",
        ),
        ("same_symbol_total_volume", "decimal", "Gross same-symbol lots in eligible snapshot"),
        ("has_SL", "boolean", "Whether entry-time observed SL is nonzero; unknown state null"),
        ("has_TP", "boolean", "Whether entry-time observed TP is nonzero; unknown state null"),
    ):
        add(name, "Position / Risk Behavior", definition, dtype=dtype)
    for name, definition in (
        ("entry_account_equity", "Entry-time account equity; later snapshots forbidden"),
        (
            "notional_exposure",
            "Entry price * confirmed volume * contract size; nominal quantity, not validated risk",
        ),
        (
            "notional_to_equity",
            "Nominal entry exposure / positive entry-time equity; not monetary risk",
        ),
    ):
        add(name, "Account Context", definition, source="ENTRY_TIME_ACCOUNT_AND_METADATA")
    for name, dtype, definition in (
        (
            "previous_episode_direction",
            "string",
            "Most recent prior known candidate/symbol episode entry direction",
        ),
        (
            "time_since_previous_entry",
            "decimal",
            "Seconds since prior entry in known candidate/symbol sequence",
        ),
        (
            "time_since_previous_exit",
            "decimal",
            "Seconds since latest confirmed prior close in that sequence",
        ),
        ("previous_entry_volume", "decimal", "Prior known sequence entry volume"),
        ("volume_ratio_vs_previous", "decimal", "Current / previous positive entry volume"),
        ("price_distance_from_previous_entry", "decimal", "Current minus previous entry price"),
        (
            "same_direction_sequence_length",
            "integer",
            "Consecutive observed entry directions within known candidate/symbol sequence",
        ),
    ):
        add(name, "Sequence / Episode", definition, dtype=dtype, source="PRIOR_CONFIRMED_EVENTS")
    for name, dtype, definition in (
        ("observation_quality", "string", "Entry event quality; never future episode confidence"),
        ("source_confidence", "string", "Attribution confidence at entry observation"),
        ("entry_time_known", "boolean", "Broker opening time confirmed by entry evidence"),
        (
            "market_context_complete",
            "boolean",
            "All six context windows meet retained configured count",
        ),
    ):
        add(name, "Data Quality", definition, dtype=dtype)
    for name, dtype, definition in (
        ("close_status", "string", "Confirmed closed versus unclosed recorded episode"),
        ("episode_confidence", "string", "Final observed episode confidence"),
        ("exit_time_known", "boolean", "Broker close time present"),
        ("gross_observed_pnl", "decimal", "Sum retained broker profit; partial episode excluded"),
        (
            "net_observed_pnl",
            "decimal",
            "Gross + signed commission + fee + swap; partial episode excluded",
        ),
        ("commission", "decimal", "Signed broker commissions for complete episode"),
        ("fee", "decimal", "Signed broker fees for complete episode"),
        ("swap", "decimal", "Signed broker swap for complete episode"),
        (
            "holding_duration",
            "decimal",
            "Confirmed full episode holding seconds; unknown entry null",
        ),
        ("episode_entry_count", "integer", "Confirmed entry/increase fills in retained episode"),
        ("increase_count", "integer", "Confirmed scale-in count"),
        ("entry_volume_sequence", "decimal_sequence", "Confirmed entry lots in broker time order"),
        ("entry_price_sequence", "decimal_sequence", "Confirmed entry prices in broker time order"),
        ("max_volume_ratio", "decimal", "Maximum successive entry lot ratio"),
        ("median_entry_spacing_time", "decimal", "Median seconds between confirmed entries"),
        (
            "median_entry_spacing_price",
            "decimal",
            "Median absolute price spacing between confirmed entries",
        ),
        ("partial_close_count", "integer", "Confirmed reductions before final close"),
        (
            "fraction_closed_first",
            "decimal",
            "First partial closed volume / exposure immediately before it",
        ),
        (
            "fraction_closed_total_before_final",
            "decimal",
            "Sum partial closed volume / total confirmed entry volume; ambiguous reversal null",
        ),
        (
            "time_to_first_partial_close",
            "decimal",
            "First partial broker time minus confirmed opening time",
        ),
    ):
        add(name, "Outcome", definition, dtype=dtype, source="POST_ENTRY_EPISODE", causal=False)
    for stop in ("SL", "TP"):
        for suffix, dtype, definition in (
            ("change_count", "integer", "Count observed modifications excluding initial state"),
            ("removed_count", "integer", "Count observed stop removals"),
            (
                "first_change_delay_observed",
                "decimal",
                "First observed modification minus confirmed open; first-observed semantics",
            ),
        ):
            add(
                stop + "_" + suffix,
                "Outcome",
                definition,
                dtype=dtype,
                source="POST_ENTRY_STOP_OBSERVATIONS",
                causal=False,
            )
    return tuple(rows)


CATALOG = catalog()
BUILDER_SOURCE_HASH = hashlib.sha256(
    b"".join(
        p.name.encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n")
        for p in sorted(Path(__file__).parent.glob("*.py"))
    )
).hexdigest()
FEATURE_SET_ID = (
    "behavioral-v1-"
    + content_id([[r.model_dump(mode="json") for r in CATALOG], BUILDER_SOURCE_HASH])[:24]
)
BY_NAME = {r.name: r for r in CATALOG}
