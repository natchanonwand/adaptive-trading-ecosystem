# Phase 3.2 preregistered benchmark registry

Baseline: `phase3.1-v0.1.0`. Preregistration fixes hypotheses before backtesting or observing profitability, preventing silent parameter changes after results become available.

| ID | Entry eligibility | Trend exit eligibility | Required observations |
| --- | --- | --- | --- |
| B01_LEGACY_HYBRID_V0 | EMA50 > EMA200 AND close > previous_high20 | None; future normal exits STOP_LOSS and TAKE_PROFIT | 250 |
| B02_EMA_TREND_50_200 | previous_fast <= previous_slow AND current_fast > current_slow | previous_fast > previous_slow AND current_fast <= current_slow | 201 |
| B03_CHANNEL_20_10 | close > previous_high20 | close < previous_low10 | 21 |
| B04_CHANNEL_55_20 | close > previous_high55 | close < previous_low20 | 56 |

All definitions are LONG_ONLY and H1_OBSERVED_BAR. Periods count successive valid observed H1 bars, not calendar hours or days. Phase 3.1 indicators continue across clock gaps without synthesizing missing bars. B02 needs the previous and current EMA200 observations, hence 201 bars. Channel windows exclude the current bar, hence 21 and 56; these also cover ATR14 availability. B01 retains its explicit 250-bar warm-up.

B01 is the original project hypothesis/control (PROJECT_LEGACY_HYPOTHESIS). B02 is a MOVING_AVERAGE_TREND_BENCHMARK. B03/B04 are CHANNEL_TREND_BENCHMARK hypotheses inspired by channel/trend concepts; H1 observed-bar horizons and simplified policies do not constitute exact historical Turtle reproductions.

Every definition declares an initial fixed Wilder ATR14 stop, conceptually signal close minus 2 ATR. Tick rounding is deferred to instrument policy. Only B01 declares FIXED_PRICE_R_MULTIPLE with multiple 2: a future implementation must derive initial price risk from actual simulated entry fill minus fixed stop, then derive the target from actual entry fill plus twice that risk. Signal close must not replace actual entry fill in this calculation. The other three declare take profit NONE. B02 future normal exits are PROTECTIVE_STOP and TREND_EXIT; B03/B04 use PROTECTIVE_STOP and CHANNEL_EXIT. These are metadata only: no stop, target, risk, fill or trade calculation occurs here. Pyramiding, averaging down, short support, trailing stops and same-bar reentry are disabled.

Pure evaluators return ENTRY_ELIGIBLE, EXIT_ELIGIBLE, HOLD_OR_NO_ACTION or UNAVAILABLE, without position state. They compose Phase 3.1 state primitives from supplied current/prior research values. Callers must supply the corresponding Phase 3.1 indicator values from valid observed bars; the evaluator does not fetch bars or recompute indicators. ATR is declared as future stop policy, not an additional entry predicate. B02 uses a transition rather than emitting repeated entries during a persistent bullish state.

Evaluation requires a completed bar with decision_time equal to bar.close_time. Current/prior inputs must be available by decision_time; prior crossing inputs must be chronological and adjacent in observed-bar count. Future execution is strictly after decision_time, with no same-close fill. Synthetic tests mutate future bars and current extrema to verify earlier eligibility and excluded-current-window semantics.

Frozen typed contracts reject unknown fields, enum values, unapproved parameters, duplicate/missing/reordered IDs and altered invariants. Validated copying cannot bypass these checks. Every definition and the registry carry research_status=PREREGISTERED_EXPLORATORY_BENCHMARK, research_classification=EXPLORATORY_RESEARCH_ONLY, qualification_eligible=false, profitability_known=false, optimized=false and literature_replication=false. No empirical validation or profitability is claimed.

Canonical identity uses UTF-8 JSON with sorted object keys, two-space indentation, a final LF, and no nonfinite numbers. Definition SHA-256 hashes exclude their own digest. The registry hash includes its schema, explicit B01/B02/B03/B04 order, full definitions and their hashes, classification and time basis; it excludes its own digest. Identities contain no timestamps, machine paths or runtime values. `research/benchmark_registry_v0.1.0.json` is source configuration intended for a future commit. Exact-byte verification against Python rejects drift, including noncanonical serialization. Parameter changes require a new explicitly versioned hypothesis or experiment; there are no setters or optimization ranges.

TSMOM: **DEFERRED_NOT_REGISTERED**. The authorization's multi-month literature horizon needs defensible daily/session aggregation across BTCUSD, XAUUSD and USTEC100. Naively converting calendar months into fixed H1 counts would produce inconsistent economic horizons. The unchanged Phase 3.1 trailing_return primitive remains available but unused by these four executable hypotheses.

Run `scripts/verify_phase3_2.ps1` with uv on PATH and TE_TEST_DATABASE_URL set for isolated PostgreSQL regression. It runs locked dependency sync, all synthetic regression tests (including fresh database and production scope checks), lint, formatting, strict typing, secret scanning, artifact verification and whitespace checks. It does not load real historical evidence. The secret scanner recognizes only five canonical digest lines in this exact artifact, and only after independent verification of the entire artifact; all other findings remain subject to existing scanning.
