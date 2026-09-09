# Test plan and acceptance gates

Status: required future verification; no tests or implementation have been run. Specification checks alone are not operational evidence.

## Component verification matrix

| Component | Required tests | Measurable acceptance |
|---|---|---|
| Ingestion | Invalid OHLC, duplicates, timezone/DST, closed sessions, missing bars, late corrections | Every invalid fixture rejected or quarantined with reason; no silent tradable fill-forward |
| Metadata | Lot/tick boundaries, effective dates, USD valuation, broker examples | Exact lot/tick compliance; P&L and margin match agreed broker fixtures within documented currency rounding |
| Snapshot storage | Hashing, immutable reimport, provenance | Same input yields same manifest; changed byte creates new hash |
| Features | Independently computed EMA/ATR vectors, seeds, equalities, gap reset | Exact Decimal values under arithmetic contract, all warm-up boundaries correct |
| Strategy | Breakout excludes t, equality, actual-fill fixed 2R TP, tick ceiling, no trailing/channel exit, long-only, partial VWAP, no same-bar reentry, duplicate/restart replay | Exact ordered intents match hand-calculated fixtures; no look-ahead or duplicate intent |
| Regime engine | Versioned classification fixtures and causal replay when introduced | Zero future-input use; deterministic labels; cannot affect V0 signals |
| News/macro | Revisions, first-seen availability, citations, prompt injection | Future revisions unavailable to past queries; research output cannot invoke execution |
| Risk | Each limit at/below/above boundary, stale quotes/accounts, min-lot, concurrency, costs | Zero unsafe admissions across fixtures; atomic multi-asset reservations stay within all limits |
| Coordinator | Crash before/after send, timeouts, duplicates, partial fills, conflicting broker state | No blind duplicate submission; unknown state pauses entries; replay preserves ledger |
| MT5 adapter | Real/unknown account refusal, rejected SL/TP, TP confirmation deadline, disconnect, order lookup, partial fills and paired-exit races | Zero real-account write calls; unprotected fills trigger cancel/close workflow and incident |
| Simulator/paper | Bid/ask gaps, fees, rollover, SL/TP chronology, equal-timestamp sequences, both-touch OHLC ambiguity, expiry, no same-close fill | Exact fixture fills/accounting; identical strategy/risk outputs for identical input streams |
| Ledger/journal | Dedupe, reversal, fills/fees, external activity, restoration | Each fill booked once; cent-rounded balance/equity identity; unexplained activity halts |
| Registry/adaptation | Alter hashes, absent/expired/revoked approval, candidate mutation | All invalid promotions and runtime releases rejected; no autonomous promotion |
| Reports | Independent metric fixtures, price RR vs net R, costs, exceptional exits, calendar days, no trades/losses, flows, missing marks | Metric equations match; N/A and incomplete states explicit; reconciliation ≤USD 0.01 |
| Dashboard | Snapshot/SL/TP totals, Trading Calendar drill-down, UTC/Bangkok grouping, all 11 animation states/precedence/reduced motion, stale/disconnect, keyboard/contrast, forged controls | All thresholds in DASHBOARD_SPEC pass; no secrets in rendered output |
| Security/config | Secret scanning, log redaction, denied routes, defaults | No committed test or real secrets; default entry-disabled; sandbox cannot reach broker writes |
| Operations | Lease loss, process restart, DB interruption, restore and reconciliation | No new writes without ownership; zero lost acknowledged journal events in crash fixtures; restored system stays paused until reconciled |

Use unit tests for pure rules, property tests for conservation/deduplication/limits, integration tests for storage and adapters, deterministic replay for engine parity, and controlled fault injection for operational controls. Seed randomized test generators and retain failing inputs. Each component must have an owner and linked test evidence before its milestone is complete. Real broker tests use a dedicated explicitly authorized demo account; mocks do not prove broker behavior.

## Owner-alignment acceptance fixtures

These are required future tests, not executed runtime evidence:

- Entry=100, stop=90, tick=0.01 gives initial_price_risk=10 and TP=120. With one unit worth USD 1 per price unit, exit=120 and total commission/financing=2 gives net R=1.8; admission cost reserve does not replace the USD 10 denominator. Slipped entry=101 with the same stop gives TP=123, without adding cost compensation.
- Partial fills of equal volume at 100.01 and 100.02, stop=90, tick=0.01 give final VWAP=100.015, raw TP=120.045, rounded TP=120.05. Verify residual cancellation, racing fills, target-version history, no market-driven target changes, and fixed SL. Late fills after an exit follow PROTECTION_FAILURE handling.
- At entry=100, SL=90, TP=120: chronological bid quotes 120 then 90 exit TP; 90 then 120 exit SL. Equal timestamps require source sequence; outcome-relevant missing sequence fails quote qualification. OHLC open=100/high=125/low=85/close=110 with an active bracket exits SL and flags intrabar_ambiguous. Known gap-open TP/SL is processed before later range touches. Every OHLC run is non-qualifying.
- SL unconfirmed closes immediately; TP rejected or still unconfirmed after 5 seconds from fill receipt triggers safety handling. Partial exits cannot leave oversized sibling orders or create shorts. Exceptional reasons remain distinct from normal TP/SL.
- Verify risk admission at 0.25% and aggregate 0.75%, plus halt at exactly 1.5% UTC daily loss and 5% drawdown. Target placement never relaxes these limits.
- An episode closing at 2026-09-09T18:00:00Z belongs to UTC September 9 and Bangkok September 10. Multi-day episode costs/net R are attributed once to close day; interval equity P/L reconciles separately. Check zero trades, N/A, mixed exit reasons, per-asset totals, and incident/annotation availability.
- All eleven decorative states, overlap precedence, three-second transient expiry, reload behavior, keyboard day navigation, and `prefers-reduced-motion` pass fixtures. Text remains authoritative when animation is disabled.
- The same frozen rules produce identical asset-normalized decisions across BTCUSD/XAUUSD/USTEC100 fixtures; no short-entry intent exists. A future bidirectional candidate must pass separate G1–G4 qualification.

## Gates

### G0 — Specification consistency

All ten documents exist, local links resolve, contracts agree on timestamps, price basis, units, fixed actual-fill 2R TP and lineage, partial fills, event timing/ambiguity, unchanged risk thresholds, price RR versus net R, Trading Calendar UTC/display-day attribution, animation states, long-only scope, and promotion modes. Record the owner-alignment review in [G0_REVIEW.md](G0_REVIEW.md). Unresolved choices have IDs/owners/effects. No implementation begins until this baseline is reviewed and the user authorizes implementation. Operational decisions can remain unresolved if their dependent phase remains blocked.

### G1 — Offline correctness

All applicable component fixtures pass; 100 repeated pinned baseline runs have identical normalized event checksums. Strategy/risk replay parity passes for backtest and paper adapters on the same input stream. All crash/fault fixtures preserve audit lineage and entry controls. Secret scanning passes. Quote/metadata/cost provenance is complete for qualification datasets.

### G2 — Historical qualification

Pre-register the candidate and evaluation windows. Quote-replay locked out-of-sample coverage must be at least 12 consecutive calendar months across all assets, with ≥100 closed portfolio episodes and ≥20 per asset. Each asset must have ≥99% of expected in-session H1 bars and no unresolved corrupt records. Missing intervals follow the reset policy and are reported; data sufficient for every simulated fill/valuation is required.

Baseline combined net return must be >0, profit factor ≥1.10 with at least one losing episode, and maximum modeled equity drawdown <5%. The cost-stress run must have nonnegative combined net return and drawdown <5%. No daily-loss or drawdown kill may trigger in a qualifying run. Per-asset results are disclosed; pooled success does not hide missing asset samples. All reconciliation and correctness checks must pass. These are proposed research filters, not statistical proof; failure rejects the candidate and cannot justify tuning against the same locked holdout.

### G3 — Forward qualification

After G2, authorize a frozen candidate for `PAPER_FORWARD` with fresh inputs, the same strategy/risk engines, and no broker orders. Require ≥30 consecutive calendar days and ≥30 closed episodes total, ≥5 per asset; extend the window until sample minima are met. Changing the candidate restarts qualification. Paper net return must be nonnegative, maximum drawdown <5%, no loss-control kill, zero unexplained reconciliation discrepancies, zero unresolved critical incidents, and ≥99% expected in-session bars. Report observation uncertainty and modeling assumptions.

Optional `DEMO_QUALIFICATION` may follow passed paper evidence with human approval for a dedicated demo account, the same or tighter risk limits, and full broker controls. It is an isolated test mode, not operational promotion. Any broker-specific behavioral defect invalidates affected evidence and requires requalification. This sequencing ensures a candidate passes both backtest and paper forward testing before it can send demo orders.

### G4 — Operational demo readiness

Require G1–G3, validated broker mapping/cost/calendar fixtures, dedicated verified demo account, authenticated human approval bound to immutable release/account, tested kill/pause/restart/restore procedures, current secrets/security checks, and no unresolved critical incidents. Perform a supervised demo smoke test covering entry, confirmed fixed SL and actual-fill-derived TP, paired exit reconciliation, fees, and reconciliation before unattended operational demo. Insufficient signals mean wait; do not manufacture strategy orders. A sandbox adapter test may verify mechanics separately but cannot count as strategy forward evidence.

### G5 — Later modules and adaptation

News, regimes, reporting enhancements, and dashboard additions pass their component tests before enablement. Any change capable of affecting executed behavior returns to G1–G4 with new evidence. Pure presentation changes require relevant UI/report regression checks and cannot change approved execution artifacts. Live trading has no acceptance gate in this baseline and remains unsupported.

## Evidence and failure policy

Record test suite/version, environment, input hashes, expected/actual results, owner, UTC execution time, and artifact hashes. Distinguish passed, failed, not run, and blocked. Never relabel incomplete evidence as passed. G2/G3 thresholds may be revised only prospectively by an explicit policy change with rationale; they cannot retroactively approve a failed candidate. Hardware-specific latency and recovery targets must be registered before operational load tests.
