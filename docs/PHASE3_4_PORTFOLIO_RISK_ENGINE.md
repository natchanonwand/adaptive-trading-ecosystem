# Phase 3.4 — Portfolio Accounting & Independent Risk Engine

PHASE3_4_DOMAIN_ONLY; qualification_eligible=false.
NO BROKER WRITES. NO STRATEGY OPTIMIZATION. NO LIVE TRADING.

The real repository is authoritative. The earlier document-only ZIP is not an
implementation dependency. This phase adds pure monetary portfolio and risk
functions without changing the Phase 2B, 3.3A/B/C code, schemas, datasets or results.

## Architecture and reuse

Strategy → `risk.TradeIntent` → `risk.engine.evaluate` → `OrderIntent` → future
execution/simulator adapter → `portfolio.Fill` → `apply_fill` → `project` → future
telemetry. Strategy input has no final volume, risk fraction or mutable policy
parameters. Unknown extra fields are rejected. Orders here are immutable data,
not broker requests or execution permission; Phase 1 entry capability stays disabled.

`accounting/` retains the existing Phase 3.4A contracts, ledger validation and
balance/NAV/UTC-day kernels. `portfolio/` adds both-side fill and position models.
`risk/` owns sizing and policy status. The frozen `portfolios/` package remains
the Phase 3.3C research aggregation package. No database migration is needed;
the existing Alembic configuration uses `migrations/`, not `alembic/`.

The portfolio `ValuationPoint` subclasses the existing equity contract solely to
reuse `_nav` and `_day`. Its legacy long-only `assets` tuple is empty; its
`observation_id` binds the complete new long/short input, retained alongside
per-episode marks in `Snapshot`. This bridge does not create fictitious positions
or book unrealized P/L as realized ledger entries. The existing kernels are not
modified. Their V0 threshold flags are descriptive; Risk Engine applies its pinned
policy to raw NAV and daily values independently.

## Numeric and valuation contract

All monetary, quantity, price and factor inputs reuse the existing bounded Decimal
validators. Arithmetic uses a fresh precision-34 ROUND_HALF_EVEN context; no
intermediate currency rounding. NaN/infinity, binary float and naive times reject.
UTC normalization and canonical tagged JSON/SHA-256 identities reuse domain helpers.
IDs and times are caller supplied; equivalent Decimal scales have identical identity.
No wall clock, I/O, random IDs, credentials or MT5 imports exist in these domains.

The explicit economics model is `LINEAR_USD_V1`, with USD account/quote currencies,
LOT quantity, USD-per-contract-unit prices, version/effective interval and validation
reference. It supplies tick size/value, USD value per price unit per lot, contract
size, volume min/max/step, margin per lot, linear plus fixed per-side commission,
and minimum stop distance. Tick value must match tick size × monetary price value.
Missing fields reject at validation; missing model/validation reference or expired
metadata rejects valuation/admission. Zero commission or margin is an explicit
supplied assumption, never a default. Other currency/model conversions are unsupported.

LONG uses actual BUY entry fills and current BID for marking/SELL exits. SHORT
uses actual SELL entry fills and current ASK for marking/BUY exits. Actual execution
prices include observed slippage/spread; accounting never deducts spread again.

`unrealized = sign × (mark − weighted_entry) × lots × monetary_price_value`.
Sign is +1 for LONG, −1 for SHORT. Gross notional is absolute lots × mark × contract
size. This is a supplied, validated linear contract, not hardcoded asset economics.

## Fills, ledger and portfolio

Multiple entry fills update VWAP as `(old_qty × old_VWAP + fill_qty × fill_price) /
(old_qty + fill_qty)`. A reduction realizes `sign × (exit − VWAP) × reduced_qty ×
monetary_price_value`, preserves remaining VWAP and subtracts quantity. Oversized
reductions, conflicting duplicate fills, inconsistent episode lineage, reopening a
closed episode and increasing after a reduction reject. Identical fill replay is
idempotent. Small partial executions may be below admission minimum; reconciliation
must account for actual fills rather than reject real residual quantities.

Each fill appends separate caller-identified REALIZED_PNL and COMMISSION entries,
including explicit zero values. Existing CASH_FLOW, FINANCING and audited ADJUSTMENT
categories remain separate. Corrections use the existing reversal/replacement
contracts, not mutation. Balance = opening cash + category totals; equity = balance
+ total marked unrealized P/L. Episode/strategy/asset attribution is retained; multiple
strategies and symbols aggregate without netting opposing gross exposure.

Used margin sums supplied-model position margin, conservatively retaining a higher
reconciled account margin if supplied. Free margin = equity − used margin; available
margin = free margin − reserved margin. Open estimated stop risk uses the nonnegative
current mark-to-stop loss plus one exit tick and remaining exit commission. Supplied
higher account risk/reservation totals are retained. Missing position valuation
makes aggregate equity/risk/margin/exposure unknown; stale known marks stay visible
but cannot admit entries. Quotes age after 5 seconds, accounts after 15 seconds.

## NAV and UTC daily loss

NAV starts at 1 at a positive-equity, empty-ledger inception valuation; units equal
initial equity. Between flows NAV = equity / units. Each external flow requires
adjacent same-time pre/post valuations, exactly one new CASH_FLOW entry, and post
equity = pre equity + flow. Units change by flow / pre-flow NAV; NAV and its running
high remain unchanged at the flow. Missing flow marks, exhausted units or stale/
incomplete NAV history stay unavailable until the caller supplies reconstructed
evidence. Precision-34 unit arithmetic may round nonterminating quotients.

Drawdown = 1 − NAV / running high NAV. Daily trading P/L = current equity − valid
UTC midnight equity − external flows since its sequence boundary; daily loss fraction
divides that P/L by boundary equity. Missing/nonpositive/stale midnight valuation is
unavailable, never zero. A flow at midnight requires a pre-flow boundary. Bangkok
midnight has no risk meaning. Risk status also evaluates the closing UTC day before
rolling to the next boundary, so a midnight loss observation cannot erase a breach.

## Pinned policies

| Limit | V0_CONSERVATIVE (default) | HR_DEMO_5PCT |
|---|---:|---:|
| New episode stop risk including costs | 0.25% | 5% |
| Open + reserved + new stop risk | 0.75% | 10% |
| Daily loss halt | 1.5% | 10% |
| NAV drawdown halt | 5% | 30% |
| Open/pending episodes | 3 | 2 |
| Per canonical asset | 1 | 1 |
| Gross notional / equity | 2.0 | 2.0 |
| Used + reserved margin / equity | 20% | 20% |
| Spread / ATR | 0.10 | 0.10 |
| Adverse entry movement / ATR | 0.25 | 0.25 |
| Direction | LONG only | LONG or SHORT |

Unchanged conservative exposure, margin, freshness and spread constraints also bound
HR because the authorization supplies no relaxed replacements. HR is allowed only
in BACKTEST, PAPER_FORWARD and DEMO_QUALIFICATION, never DEMO_OPERATIONAL. REAL and
UNKNOWN account types reject for both profiles; demo modes require DEMO identity.
The new authorization permits short domain support for HR only; frozen V0/simulator
long-only semantics remain untouched. These engineering profiles are not qualification.

For candidate q, entry price is ASK for long or BID for short. Stop risk =
`q × ((entry-to-stop distance + 2 ticks) × monetary_value + 2 × per_lot_commission)
+ 2 × fixed_commission`. The two ticks preserve the V0 entry/stop adverse allowances.
The actual bid/ask entry basis embeds spread, so it is not added twice.

Risk searches the explicit broker lattice `volume_min + n × volume_step`, n ≥ 0,
bounded by volume_max. Integer-ratio bounds and monotonic binary search avoid an
upward-rounded risk-budget quotient. Stops must already be on the price tick lattice;
the engine never moves them. If the minimum volume violates any limit, reject.
The final volume is checked again with exact integer ratios; if its lattice offset
cannot be represented at Decimal34 precision, admission rejects explicitly.

V0 selects the largest lattice volume satisfying all limits, as RISK_POLICY requires.
HR selects its 5%-budget volume first, then rejects if aggregate/margin/exposure
capacity is insufficient. It never silently shrinks a requested 5% experiment to
remaining portfolio capacity: existing 7% plus requested 5% exceeds 10% and rejects.

## State, reservation and future boundaries

ACTIVE requires trusted valuation, known daily/NAV baselines, positive equity,
healthy reconciliation/broker/lease/protection, active approval and validated open
session. Missing/unknown/stale data yields PAUSE_ENTRIES. Daily/drawdown equality
triggers HALT_AND_FLATTEN, as does an explicit severe breach. Threshold comparisons
use exact integer ratios before display rounding. Historical breaches in supplied
observations and prior HALT state remain latched through recovery. Cross-account,
future or changed-policy prior states reject. No automatic or human-reset API is
implemented; a later audited operator workflow must own reset.

`evaluate_and_reserve` returns the decision and a new history with the reservation.
Subsequent serial requests see its risk, margin, notional and asset occupancy. The
caller must persist that transition with an atomic account-version compare-and-swap;
this pure phase does not claim a distributed transaction or broker delivery guarantee.
Reservations do not expire/release automatically. Partial-fill residual reservation
updates, cancellation confirmation, protection installation and reconciliation are
future coordinator duties. Every order binds its input identity and a lifetime
bounded by five seconds, intent expiry, quote/account freshness and economics validity.

Sampling is caller-defined; unobserved intraday peaks/losses cannot be inferred.
Full-history performance/status replay favors correctness over production throughput.
Broker D01 economics validation, calendars, authenticated approval, operational state
restoration, broker adapters, and monitoring persistence remain future work.

## Verification

`scripts/verify_phase3_4.ps1` runs the existing full Phase 2B and Phase 3.3B gates,
including locked sync, all tests, fresh migrated PostgreSQL, Ruff, format, strict
mypy and secret scans; it additionally verifies frozen Phase 3.3C aggregation and
compares every dataset/research file hash before/after. `-CodeOnly` runs the complete
code gate without the lengthy real-evidence reads. New unit/property tests and a
PostgreSQL journal roundtrip exercise Strategy Intent → Risk → synthetic Fill →
Accounting without changing production persistence code. STOP before Phase 3.5.
