# Strategy V0: H1 long-only trend breakout

Status: testable hypothesis, not an approved trading strategy. Applies identically to BTCUSD, XAUUSD, and USTEC100, subject to valid instrument metadata and session availability.

## Inputs and arithmetic

Use completed H1 bid-price OHLC bars aligned to UTC hours. A broker/source unable to provide compatible bid history cannot qualify under V0. No forming bar, news, LLM output, or diagnostic regime label enters this strategy. Scheduled session gaps do not synthesize bars; indicator periods count actual valid session bars. An unexpected missing expected bar resets indicator warm-up and blocks entries. Existing positions retain their fixed stop and take-profit independently of indicator warm-up.

Use the arithmetic contract in [DATA_MODEL.md](DATA_MODEL.md). EMA(n) is seeded with the mean of the first n closes, then `EMA_t = alpha*close_t + (1-alpha)*EMA_(t-1)`, alpha=2/(n+1). TR for the first bar is high−low; subsequent TR is max(high−low, abs(high−previous_close), abs(low−previous_close)). ATR(14) is the mean of the first 14 TR values, then Wilder smoothing `(13*previous_ATR + TR)/14`. Require 250 valid bars after initialization/reset before entry evaluation. ATR must be positive.

## Entry

At close of bar t, when flat with no pending entry, emit ENTER_LONG only if all hold:

1. `EMA50_t > EMA200_t`.
2. `close_t > max(high_(t-20), ..., high_(t-1))`.
3. All required bars, indicators, and mapping versions are valid.

Strict comparisons mean equality produces no entry. Indicator values include t; the breakout window excludes t. Proposed stop is `close_t − 2*ATR14_t`, rounded down to a valid price tick. The risk engine derives final volume from the executable ask, stop, costs, and portfolio limits. Nonpositive stop, invalid broker distance, or insufficient volume rejects the intent. Do not move the stop farther away to make an entry acceptable.

## Fixed 1:2 price risk/reward and exits

Every normal V0 episode has a fixed stop and a fixed take-profit (TP), with conceptual price risk/reward 1:2. After actual entry execution:

- `entry_fill_price` = actual fill price, or volume-weighted actual entry fills for a partial-fill episode.
- `initial_price_risk = entry_fill_price - fixed_stop`; it must be positive.
- `take_profit_raw = entry_fill_price + 2 * initial_price_risk`.
- `take_profit = ceil(take_profit_raw / tick_size) * tick_size`, using the Decimal contract in [DATA_MODEL.md](DATA_MODEL.md). Upward tick rounding preserves at least the conceptual 2R price distance; record the rounding delta and effective price RR.

The stop remains the tick-rounded signal stop. Commissions, spread, financing, and execution slippage affect net R; they never shift the target to compensate for costs. Actual entry slippage is already part of the actual entry fill used by this formula. The target is not a guaranteed net +2R outcome. No trailing stop is used. There is no bar-channel or other normal signal-based exit. Normal exits are STOP_LOSS and TAKE_PROFIT only.

For partial entry fills, cancel the remaining entry quantity on first partial execution. Reconcile any racing fills. Each observed fill updates cumulative actual-fill VWAP and a versioned provisional target for that filled quantity; the stop never moves. Freeze the final VWAP, initial price risk, and target once the entry is confirmed terminal. These fill-driven revisions are entry completion, not trailing or market-based adaptation. If an exit begins before entry becomes terminal, cancel/reconcile residual entry and close any late-filled remainder as PROTECTION_FAILURE; retain every target version and fill association. This is an exceptional episode, not normal target completion.

Broker-side SL/TP confirmation, target amendment, and protection failure handling follow [ARCHITECTURE.md](ARCHITECTURE.md). If the target cannot be installed at the calculated price, do not choose a different RR: cancel residual entry and close as PROTECTION_FAILURE. Risk/safety exits (RISK_SAFETY), authenticated operator flattening (OPERATOR_FLATTEN), protection failures (PROTECTION_FAILURE), and forced evaluation-boundary exits (EVALUATION_BOUNDARY) are permitted and reported separately. A partial exit retains the frozen stop/target for remaining quantity and must never open a short position.

No pyramiding, short positions, averaging down, or same-bar reversal. Do not enter on a signal bar during which that asset had any position or entry fill, even if SL, TP, or an exceptional exit closes it before the close. A subsequent completed bar may create a new entry. A rejected or expired entry is not retried from the same bar; a new qualifying close is required.

## Timing and state

Decision time is bar availability after close. Execution must be strictly later than decision time. An entry expires five minutes after decision time and is canceled if not executable by then; it does not wait through a market closure. Exits remain pending until executable or reconciled flat. Market-order requests use current quotes; simulator fills use the first eligible quote/next bar open described in [BACKTEST_SPEC.md](BACKTEST_SPEC.md).

State: warmed indicator history, last processed bar, flat/open/pending status, episode ID, actual-fill VWAP, fixed stop, initial price risk, raw/rounded TP, target version/frozen status, SL/TP protection status, and last bar containing exposure. Durable order/position truth comes from reconciliation, not from assuming an intent filled. Exact duplicate events have no effect; conflicting duplicates are data incidents.

## Parameters and change control

| Parameter | V0 value |
|---|---:|
| Timeframe | H1 |
| EMA fast/slow | 50 / 200 |
| Entry breakout | 20 bars |
| Fixed price risk/reward | 1:2 (TP at 2R, upward tick rounding) |
| ATR period / stop multiplier | 14 / 2 |
| Entry warm-up | 250 valid bars |
| Entry intent expiry | 5 minutes |

These parameters are frozen per release. No symbol-specific optimization is included. Changing any rule, parameter, arithmetic, or input basis produces a new candidate requiring backtest and forward evidence. Cross-asset and regime performance must be reported even when pooled results pass. Acceptance tests include exact indicator fixtures, boundaries, missing bars, restarts, partial fills, and shared-engine replay parity in [TEST_PLAN.md](TEST_PLAN.md).

V0 is intentionally long-only and identical across all three assets. Bidirectional short support is a later candidate strategy requiring a separate specification and full backtest/forward qualification; it is not a runtime toggle.
