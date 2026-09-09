# Independent risk policy

Status: proposed V0 engineering limits; owner approval required before qualification. The strategy cannot override this policy.

## Default limits

| Control | V0 limit |
|---|---:|
| New episode estimated loss at stop, including costs | ≤0.25% of current equity |
| Sum of open and reserved estimated stop losses | ≤0.75% of current equity |
| Open or pending episodes | ≤3 total, ≤1 per asset |
| Gross USD notional / equity | ≤2.0 |
| Projected used plus reserved margin / equity | ≤20% |
| Spread / current ATR14 | ≤0.10 |
| Adverse entry movement from signal close | ≤0.25 ATR14 |
| Quote age at approval and submission | ≤5 seconds |
| Account snapshot age at approval and submission | ≤15 seconds |
| Maximum risk approval lifetime before submission | 5 seconds, also bounded by entry expiry |
| UTC daily flow-adjusted equity loss | ≥1.5% triggers halt and flatten |
| Flow-adjusted equity drawdown from running high | ≥5% triggers halt and flatten |

All upper bounds are inclusive except stated trip conditions, which trigger at equality. Gross notional uses absolute exposure; no diversification offsets are assumed. Pending volume reserves risk, notional, and margin. Open risk is recomputed as nonnegative estimated loss from current bid to fixed stop plus remaining exit costs. Gaps and slippage can exceed estimated stop risk; limits are admission controls, not guaranteed maximum losses.

## Position sizing and admission

For each candidate quantity q, use the instrument's validated USD valuation model to compute loss from current ask to the fixed stop, plus round-trip commission and a one-tick adverse entry and one-tick adverse stop-fill allowance. Financing uses the pinned schedule in reporting/simulation but is not a bounded holding-period reserve; unbounded holding time makes that impossible. Reject missing cost, valuation, margin, calendar, or account metadata.

Choose the largest broker-valid lot-step quantity satisfying every limit, rounded down and bounded by instrument maximum. Reject if below minimum lot. Require positive equity, confirmed demo account, active approval, market session, fresh quote/account, acceptable spread/gap, valid stop distance, no conflicting pending request, healthy reconciliation, and a valid account lease. Preserve the fixed stop; reject if executable ask is at or below it.

Serialize reservations across assets. Immediately before submit, refresh checks and reject/re-evaluate expired decisions; never submit an expired risk token. If a partial fill or price change breaches limits, cancel residual entry, block additional entries, and reconcile. If filled exposure itself exceeds admission limits, request a full close of that episode; never increase another position to compensate.

## Fixed bracket validation

The 2R price target does not increase any admission budget: 0.25% new-episode stop risk and 0.75% total open/reserved stop risk remain unchanged. Cost-inclusive admission risk is distinct from the cost-exclusive initial price-risk denominator used for net R reporting. Require fixed SL and post-fill TP support. Independently verify `initial_price_risk = actual_entry_VWAP - fixed_stop > 0` and `take_profit = ceil((actual_entry_VWAP + 2 * initial_price_risk) / tick_size) * tick_size`. Reject invalid distances; do not move SL or compensate costs by changing target RR.

Missing SL is an immediate protection failure. TP_PENDING is allowed only during the bounded five-second post-fill receipt confirmation workflow in [ARCHITECTURE.md](ARCHITECTURE.md); pause additional account entries until confirmed. Invalid/rejected/timed-out TP triggers cancellation and PROTECTION_FAILURE close. On partial entries, cancel residual quantity and reconcile racing fills before freezing target/VWAP; every bracket revision is audited. SL and TP must remain attached to remaining exposure during pauses. Normal exits are SL/TP, not a bar-channel signal. Risk/safety, operator, protection-failure, and evaluation-boundary exits retain distinct reasons. Sell volume cannot exceed reconciled long quantity; bidirectional short support is outside V0 and requires separate qualification.

## Runtime controls

- **Pause entries:** stop accepting entries and cancel outstanding unfilled entry quantities; keep fixed SL/TP and exceptional exits active.
- **Kill/flatten:** latch pause, cancel entries, request full close of all exposure, reconcile until confirmed flat. Failures remain visible and cannot be acknowledged as success.
- **Daily loss:** use UTC midnight boundary equity and net external flows since boundary: `(equity − boundary_equity − net_flows)/boundary_equity`. Trigger at ≤−1.5%. If no valid midnight valuation exists, block entries until reconstructed. A daily halt requires the next UTC day, healthy reconciliation, and human reset.
- **Drawdown:** compute high-water mark on flow-adjusted NAV as defined in [REPORT_SPEC.md](REPORT_SPEC.md). Trigger at ≥5%. No automatic reset; investigation and human approval are required. NAV baseline cannot be reset just to remove a breach.
- **Health halt:** stale data, disconnected broker, unexpected account activity, unknown submission, or loss of protection pauses account entries. Keep stop protection at the broker; send exits only when connectivity and ownership permit.

During scheduled closures quotes may age without triggering spurious executable orders. Entries are ineligible while closed; before reopening, all freshness and reconciliation checks must pass. Loss of ability to value an open portfolio marks equity unknown and pauses entries. Simulations apply loss checks at every modeled valuation point; demo applies them on broker snapshots at least every five seconds when connected. Reports distinguish these monitoring resolutions.

No credentials or privileges are granted to strategy/LLM processes. Account identity and demo flag are checked on startup, reconnect, and before writes. Unknown account type or a real account is a hard rejection. Live enablement requires a separate future design and is not a configuration switch in V0.

## Exit exceptions and audit

Risk-reducing exits bypass entry sizing, exposure, spread, and daily-loss admission limits; they still require verified demo identity, correct position quantity, account ownership, and request deduplication. Revoked or expired strategy approval cannot prevent an independently authorized protective close or cancellation. SL or TP removal without confirmed closure or safe replacement is forbidden. Every rejection, halt, reset, cancellation, and operator action is journaled with policy version and evidence.

See [TEST_PLAN.md](TEST_PLAN.md) for exact boundary, stale-state, concurrency, unknown-order, and kill-switch tests. D01, D02, D04, and D05 must be resolved before broker qualification.
