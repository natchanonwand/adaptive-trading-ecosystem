# Phase 4A — MT5 Read-Only Bridge & Broker Validation

Status: PASS — Phase 4A read-only bridge implementation, full regression and real
DEMO observation smoke completed on 2026-09-22 (Asia/Bangkok). Broker economics
remain PARTIAL and are not qualification-sizing eligible. No execution or
Phase 4B work has started.

## Checkpoint

Local branch `phase4a-mt5-readonly`; checkpoint `6147c75`:
`feat: complete portfolio risk monitoring foundation through phase 3.6`.
All 81 validated Phase 3.4–3.6 additions were checked against the prior reports,
777-test results and preserved hashes. Secret scan passed before checkpoint.
One trailing empty report line was removed for staged whitespace validation.
No generated data, screenshots, terminal configuration or credentials were
committed. No push or tag was performed. Phase 4A remains a separate working diff.

## Acceptance

| Check | Result |
| --- | --- |
| Baseline checkpoint | PASS |
| MT5 initialize and DEMO detection | PASS, actual terminal |
| Terminal/account telemetry | PASS |
| Positions / active orders | PASS, valid empty state on real account; nonempty fake coverage |
| Deal and order history | PASS, 131 distinct deals / 123 historical orders in initial window |
| Quote telemetry / discovery / explicit aliases | PASS |
| BTCUSD economics | PARTIAL |
| XAUUSD economics | PARTIAL |
| USTEC100 economics | PARTIAL |
| Canonical telemetry and journal persistence | PASS |
| Idempotency / restart recovery | PASS, same 131 deals after restart |
| Reconciliation | PASS, fake additions/closures/reversals and missing/changed projections |
| Monitoring API / SSE | PASS, actual demo scope |
| Dashboard real data | PASS, no MOCK DATA; DEMO/CONNECTED; no JS errors |
| Read-only invariant | PASS, explicit SDK read allowlist |
| Trading submission references/calls in Phase 4A source | ZERO |
| Targeted tests including prior monitoring/scope | 108 PASS |
| Full Python / PostgreSQL regression | PASS — 836 tests, zero failures/errors/skips |
| Frontend tests | PASS — 61 tests; actual API fixture also exercises two TS integration cases |
| TypeScript strict / ESLint / Prettier / production build | PASS |
| Ruff / Ruff format / strict mypy | PASS — 186 formatted files; 154 typed source files |
| Secret scan | PASS — 242 project files, zero findings |
| Phase 2B–3.6 regression | PASS — all original historical verifiers completed |
| Frozen evidence | All 874 files byte-for-byte unchanged |
| Prior working files during full gate | All 46 unchanged from the explicit Phase 4A gate baseline |

Final evidence: `test-results/phase4_a-full-gate.log`,
`test-results/phase4_a.xml`, `test-results/phase3_6-frontend.xml`.
The final 836-test run includes the additional Decimal-context UTC regression.
Phase 3.3B verified the existing 12 results and split boundaries without new
historical simulations; Phase 3.3C verified its existing replay/report. All
original tagged files, domain risk/accounting policies and historical evidence
remain unchanged. The six intentional integration-file changes are listed below;
the 46-file gate comparison does not claim those six changes never occurred.

## Real environment and smoke evidence

Observed Windows 11 build 26200, Python 3.12.14, MetaTrader5 package 5.0.6180,
terminal build 6182 (5 September 2026), MetaQuotes MetaTrader 5. Broker:
Exness Technologies Ltd, server Exness-MT5Trial14. Trade mode 0 (DEMO), USD,
leverage 2000. Terminal connected; trade_allowed=false; tradeapi_disabled=false;
observed ping_last=64529 (native units). None of these flags grants execution
authority. The logged-in identifier was scoped to a pseudonymous UUID, not logged.

The terminal catalog contained 356 symbols. Visible Market Watch names were
BTCUSDm, XAUUSDm and USTECm; the explicit example aliases were checked against
that live catalog. No selection or fuzzy matching was performed.

Initial 45-second smoke: 31 successful cycles, zero failed cycles. Restart
120-second smoke: 80 successful cycles, zero failures. Initial/restart deal
count stayed 131. Final accepted 50-second smoke: 24 successful cycles, zero
failures, CONNECTED; 824 verified journal events before graceful stop, still
131 distinct deals and 123 historical orders. History and pending orders remain distinct from positions.
The observed account reported zero balance/equity/profit/margin/free margin and
zero open positions/orders; the dashboard displayed those broker-reported zeros.
Unavailable lifetime P&L, drawdowns, reserved risk/count and risk state remained
unknown. No trade or deposit was created to change the fixture conditions.

Local ignored evidence:

- `.local/phase4_a/demo-smoke-initial.json`
- `.local/phase4_a/demo-smoke-restart.json`
- `.local/phase4_a/demo-smoke-final.json` (final implementation run)
- `.local/phase4_a/demo-smoke-accepted.json` (accepted health/socket handling)
- `test-results/phase4_a-real-browser.json`
- `test-results/phase4_a-independent-readback.json`
- [Real Overview](test-results/phase4_a-real-overview.png)
- [Real Portfolio](test-results/phase4_a-real-portfolio.png)
- [Real Systems](test-results/phase4_a-real-systems.png)

Browser review used actual loopback API/SSE, not mock fixtures. Real nonempty
position/order lifecycle changes were not induced; these are covered with fakes.
Independent database readback verified all 825 post-stop journal events, 787
observation hashes, 131 unique deals, checkpoint hash and graceful-stop health.
Numeric normalization uses the repository's fresh Decimal34 context, including
UTC millisecond conversion and observed bid/ask spread.

## Observed instrument economics

| Field | BTCUSD / BTCUSDm | XAUUSD / XAUUSDm | USTEC100 / USTECm |
| --- | --- | --- | --- |
| Digits | 2 | 3 | 2 |
| Point | 0.01 | 0.001 | 0.01 |
| Tick size | 0.01 | 0.001 | 0.01 |
| Tick value, profit/loss | 0.01 / 0.01 / 0.01 | 0.1 / 0.1 / 0.1 | 0.01 / 0.01 / 0.01 |
| Contract size | 1 | 100 | 1 |
| Min / max lot | 0.01 / 200 | 0.01 / 200 | 0.05 / 500 |
| Lot step | 0.01 | 0.01 | 0.01 |
| Stops / freeze level | 0 / 0 | 0 / 0 | 0 / 0 |
| Profit / margin currency | USD / BTC | USD / XAU | USD / USD |
| Margin initial / maintenance | 1 / 0 | 0 / 0 | 0 / 0 |
| Trade mode / calculation mode | 4 / 5 | 4 / 0 | 4 / 2 |
| Status / sizing eligible | PARTIAL / false | PARTIAL / false | PARTIAL / false |

Metadata is internally compatible with the sampled linear USD tick/contract
relationship, but does not validate the Phase 3.4 fixed margin/commission cost
model. Zero margin metadata is not treated as zero required margin. The adapter
refuses qualification sizing without separately reviewed costs. No calculation
or trading API was invoked. Machine-readable, credential-free metadata:
[`reports/mt5_broker_economics.json`](reports/mt5_broker_economics.json).

## Integration decisions and deviations

- Existing optional discovery dependency and native loader reused; no new package.
- Account lifetime totals and portfolio reserved fields now support explicit null
  when unknown. Existing complete-account requirements remain enforced.
- Monitoring symbols accept broker labels; domain assets/policies remain frozen.
- Additive EXTERNAL_OBSERVATION activity links immutable broker facts by canonical
  hash, preserving pending orders/deals/quotes/metadata without inventing fills.
- Dashboard adds Used margin and subscribes to the new observation event.
- A prior scope test assumed later phases would remain untracked. After the
  authorized checkpoint, it now checks all frozen tag paths directly, including
  deletions. The old SDK import guard was preserved; implementation uses its
  existing loader instead of adding another native import.
- Phase 3.6 verifier accepts an explicit baseline manifest for next-phase
  integration. Its original default and historical checks remain. The original
  pre-3.6 capture is preserved; the Phase 4A gate validates its explicit diff
  allowlist and captures all 46 files before/after the composed gate.
- Secret scan initially detected a synthetic password string in a privacy test.
  The test now supplies a non-string sentinel to verify discarding secret fields;
  scanner rules were not changed.
- Actual browser review exposed normal Windows SSE socket-abort tracebacks on
  navigation; the bridge's local API wrapper handles expected ConnectionError
  while preserving unexpected server errors. Quote/database heartbeats now
  refresh their visible timestamps; economics remains visibly DEGRADED/PARTIAL.

## Limitations and stop point

Metadata-first broker economics remain PARTIAL and not sizing-qualified. Only
DEMO/USD is supported in this phase. History completeness is bounded by configured
start/overlap; late corrections outside overlap require explicit review. Imported
deals do not synthesize historical position episodes, account P&L or research
qualification. Broker/account/source metadata is observed, not strategy attribution.

The inherited journal performs chain replay on each append. The smoke validates
correctness at this scale, not long-running throughput/retention. API pressure,
storage growth and terminal disconnect recovery on the actual workstation need
further operational review; deterministic failures/restarts are covered by fakes.
The frozen Phase 3.3B verifier can emit an existing Pydantic deprecation warning.

No execution, EA cloning, behavior inference, optimization, or Phase 4B choice.
Stop for review of broker economics, identities, account mode and reconciliation.
See [startup and architecture](docs/PHASE4_A_MT5_READONLY_BRIDGE.md).

## Files added (19)

- `PHASE4_A_REPORT.md`
- `config/mt5_readonly.example.json`
- `docs/PHASE4_A_MT5_READONLY_BRIDGE.md`
- `reports/mt5_broker_economics.json`
- `scripts/start_mt5_monitor.ps1`
- `scripts/verify_phase4_a.ps1`
- `src/trading_ecosystem/mt5/__init__.py`
- `src/trading_ecosystem/mt5/__main__.py`
- `src/trading_ecosystem/mt5/bridge.py`
- `src/trading_ecosystem/mt5/client.py`
- `src/trading_ecosystem/mt5/config.py`
- `src/trading_ecosystem/mt5/economics.py`
- `src/trading_ecosystem/mt5/mapping.py`
- `src/trading_ecosystem/mt5/normalization.py`
- `src/trading_ecosystem/mt5/store.py`
- `tests/integration/test_mt5_bridge.py`
- `tests/mt5/__init__.py`
- `tests/mt5/fake.py`
- `tests/mt5/test_boundaries.py`

## Files modified (6)

- `dashboard/src/components.tsx`
- `dashboard/src/types.ts`
- `scripts/verify_phase3_6.ps1`
- `src/trading_ecosystem/monitoring/contracts.py`
- `src/trading_ecosystem/monitoring/projections.py`
- `tests/accounting/test_scope.py`

Dependencies added: none. Generated database state, smoke JSON, logs and screenshots are Git-ignored.
