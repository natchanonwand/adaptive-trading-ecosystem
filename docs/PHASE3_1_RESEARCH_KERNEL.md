# Phase 3.1 deterministic research kernel

`trading_ecosystem.research.indicators` contains pure mathematical primitives for exploratory H1 research. No strategy edge, profitability or optimal parameters are claimed. No benchmark period is privileged or defaulted. There is no backtester, trade simulation, execution, portfolio accounting, parameter search or later-phase implementation.

## Inputs and results

Bar functions accept only immutable Phase 2B `Bar` contracts in strictly increasing open-time sequence. Duplicate times, mixed datasets/assets/metadata references and invalid contracts fail explicitly, including objects bypassing normal model validation. No artifacts are read or mutated; no provider/SDK is imported by the kernel.

Use `observed_closes(bars)` to obtain the authoritative Decimal sequence for `sma(values, period)`, `ema(values, period)` and `trailing_return(close, lookback)`. Scalar functions accept finite Decimal values only, never float, text or missing input values. Invalid observations are rejected, not skipped. Return inputs must be positive closes. Period/lookback must be a positive integer; booleans are rejected. Empty inputs produce empty tuples.

Every result is an immutable tuple aligned one-for-one with the input observations. `None` means warm-up unavailable. A period longer than the input produces only `None`. Bar windows count successive observed valid bars, not elapsed clock hours. Existing datasets and derived research remain `EXPLORATORY_RESEARCH_ONLY`, `qualification_eligible=false`; nothing establishes Bid basis or upgrades current metadata to historical validity.

## Formulas and exact conventions

Indices below are zero-based; `p` is period and `L` is lookback.

| Primitive | Calculation | First available index |
|---|---|---:|
| SMA | Arithmetic mean of `x[t-p+1:t+1]`, including current value | `p-1` |
| EMA | Seed with mean of first `p` values; `alpha=2/(p+1)`; then `alpha*x[t] + (1-alpha)*EMA[t-1]` | `p-1` |
| True Range | First: `high-low`. Thereafter: `max(high-low, abs(high-previous_close), abs(low-previous_close))` | `0` |
| Wilder ATR | Mean of first `p` TRs; then `((ATR[t-1]*(p-1))+TR[t])/p` | `p-1` |
| Previous high | Maximum of `high[t-p:t]`, excluding current bar | `p` |
| Previous low | Minimum of `low[t-p:t]`, excluding current bar | `p` |
| Trailing return | `(close[t]-close[t-L])/close[t-L]`, a fractional return; no percentage scaling or annualization | `L` |

Means sum left-to-right in observation order, from Decimal zero. SMA recomputes each trailing mean directly, avoiding accumulated sliding-sum rounding. EMA computes alpha and its complement once; multiplication precedes addition exactly as written above. Period 1 makes SMA/EMA equal the current input and ATR equal TR. Previous extrema and return still need one previous observation when period/lookback is 1.

## Decimal policy

The existing `decimal34-half-even-v1` arithmetic context supplies a fresh **34-significant-digit, ROUND_HALF_EVEN** context for every calculation and bar revalidation. Each arithmetic operation rounds in that context, including recurring division, initialization and recursion. No binary floats or indicator libraries are used. Comparisons/extrema select exact Decimal values without rounding. Scalar inputs retain the existing finite Decimal boundary (34 digits, exponent magnitude at most 100); no fixed-scale quantization is applied to outputs. Caller precision, rounding, exponent limits, flags and traps cannot alter results and are not modified. Tests include hand-computable recursions, recurring fractions and context isolation.

## Gaps and causality

`gap_metadata(bars)` returns immutable records aligned with the same bars. `preceded_by_gap` is true when consecutive H1 opens differ by more than one hour. `elapsed_clock_hours` records that separation (first observation: `None`). `gap_duration_hours` is the open-to-open separation for a gap, otherwise zero; `missing_clock_hours` is separation minus one, otherwise zero. For opens at hours 1 and 5, duration is 4 and missing hours is 3. These are explicitly distinct quantities.

No leading gap can be inferred from the first supplied bar without a requested-window context. Observed gaps remain unclassified. There is no filling, calendar assumption or automatic reset. Metadata does not change calculations. For valid chronological inputs, output at `t` depends only on observations through `t`; previous extrema depend only on observations strictly before `t`. Prefix and future-mutation tests cover every indicator, state and gap output. Invalid sequences are rejected as a whole rather than partially evaluated.

## Stateless benchmark classifications

- `moving_average_state(fast_ma, slow_ma)`: BULLISH for `>`, BEARISH for `<`, NEUTRAL for equality.
- `channel_breakout_state(close, previous_high, previous_low)`: UPSIDE_BREAKOUT for strict `close > high`, DOWNSIDE_BREAKOUT for strict `close < low`, otherwise INSIDE. Equality stays inside; reversed bounds are rejected.
- `momentum_state(trailing_return)`: POSITIVE, NEGATIVE or FLAT according to comparison with zero.

Each returns UNAVAILABLE when required valid inputs are `None`; malformed supplied numeric values always raise. These are mathematical classifications only, with no stateful trading behavior.

## Verification

Run `scripts/verify_phase3_1.ps1` with `uv` on PATH and the existing isolated PostgreSQL test URL configured. It runs all prior and new tests, fresh PostgreSQL regression, Ruff, format, strict mypy, secret scanning, Git whitespace and static scope checks. It does not load or scan complete real historical datasets. Only this package, its tests, this document and its verification script are added; frozen Phase 2B implementation and dependencies remain unchanged.
