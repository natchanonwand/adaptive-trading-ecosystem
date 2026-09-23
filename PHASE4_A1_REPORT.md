# Phase 4A.1 — Broker Economics Calibration & Risk-Engine Cross-Validation

Status: COMPLETE / PASS — real DEMO calibration, independent evidence replay and
the complete Phase 2B–4A.1 gate passed. Broker economics remain PARTIAL and are
not ready for qualification sizing. Completion reviewed on 2026-09-23
(Asia/Bangkok); the accepted broker capture is dated 2026-09-22 UTC.

Phase 4A local checkpoint: `c1e354c` (`feat: add read-only MT5 monitoring bridge`). No push/tag. Phase 4A.1 remains an uncommitted diff.

Captured: 2026-09-22T13:12:42.848398+00:00. Broker: Exness Technologies Ltd / Exness-MT5Trial14. Terminal build 6182; USD DEMO, currency digits 2, leverage 2000. No account identifier or credentials are published.

## Results

| Asset / broker symbol | P/L | Margin estimate | Volume lattice | Commission | Spread | Swap | Stop constraints | Overall / sizing ready |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BTCUSD / BTCUSDm | VALIDATED sampled grid | VALIDATED local estimate | VALIDATED | OBSERVED_ONLY | OBSERVED | OBSERVED_ONLY | OBSERVED_ONLY | PARTIAL / NO |
| USTEC100 / USTECm | VALIDATED sampled grid | VALIDATED local estimate | VALIDATED | OBSERVED_ONLY | OBSERVED | OBSERVED_ONLY | OBSERVED_ONLY | PARTIAL / NO |
| XAUUSD / XAUUSDm | VALIDATED sampled grid | VALIDATED local estimate | VALIDATED | OBSERVED_ONLY | OBSERVED | OBSERVED_ONLY | OBSERVED_ONLY | PARTIAL / NO |

Qualification remains false. Observed commission/swap cannot establish a contractual future schedule. Stop/freeze distances are metadata observations, not tested order acceptance. The adapter refuses real sizing admission.

## Profit and sizing matrix

### Captured broker inputs

| Field | BTCUSDm | XAUUSDm | USTECm |
| --- | ---: | ---: | ---: |
| Bid / ask | 86044.76 / 86054.76 | 4339.709 / 4339.969 | 30511.04 / 30512.16 |
| Digits | 2 | 3 | 2 |
| Point / tick size | 0.01 / 0.01 | 0.001 / 0.001 | 0.01 / 0.01 |
| Tick value / profit / loss | 0.01 / 0.01 / 0.01 | 0.1 / 0.1 / 0.1 | 0.01 / 0.01 / 0.01 |
| Contract size | 1 | 100 | 1 |
| Min / max / step lots | 0.01 / 200 / 0.01 | 0.01 / 200 / 0.01 | 0.05 / 500 / 0.01 |
| Stops / freeze points | 0 / 0 | 0 / 0 | 0 / 0 |
| Stops / freeze price distance | 0 / 0 | 0 / 0 | 0 / 0 |
| Minimum-lot margin BUY / SELL, USD | 2.15 / 2.15 | 2.17 / 2.17 | 3.81 / 3.81 |

These are capture-time quotes and operation estimates. Zero stop/freeze metadata
does not establish that arbitrary stops will be accepted. Both sides and every
sampled volume are retained in the machine-readable report.

| Asset | Profit rows | Maximum absolute error USD | Margin rows | Risk rows | Accepted | Rejected |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTCUSD | 48 | 0.00800 | 8 | 48 | 10 | 38 |
| USTEC100 | 48 | 0.00500 | 8 | 48 | 10 | 38 |
| XAUUSD | 48 | 0.002000 | 8 | 48 | 7 | 41 |

Matrix: 3 assets × BUY/SELL × 4 stop distances × 3 equity levels × 2 policies = 144 scenarios. Equity $300/$3,000/$30,000; stops 100/10,000/200,000/500,000 ticks. All 27 accepted candidates satisfy broker stop-loss budget and simulated margin cap; 117 reject. V0 SELL is rejected under the unchanged long-only rule. HR remains the separate experimental policy.

Each accepted candidate is calculated by the original pure Risk Engine; strategies never select final lot. Its predicted risk includes the two-tick buffer plus explicit synthetic $1/lot/side and $0.01/side commissions. These are conditional experiment assumptions, not broker cost evidence. Swap remains unmodeled for the instantaneous stop experiment. Simulated health and UTC-day cash snapshots are explicit.

| $300, 200,000-tick stop | Minimum lot | Broker stop loss BUY / SELL | V0 budget | HR budget | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| BTCUSD | 0.01 | 20.0 / 20.0 | 0.75 | 15 | Minimum lot exceeds both budgets; rejected |
| USTEC100 | 0.05 | 100.0 / 100.0 | 0.75 | 15 | Minimum lot exceeds both budgets; rejected |
| XAUUSD | 0.01 | 200.0 / 200.0 | 0.75 | 15 | Minimum lot exceeds both budgets; rejected |

Observed account margin/free margin: $0.0 / $0.0. All accepted simulation candidates exceed actual observed free margin. No live-account acceptance is implied. Calculator margin is an incremental proposed-operation estimate, never total portfolio margin. Observed account fields are not changed.

## Costs and spread observations

131 unique historical deals, zero duplicate tickets; 787 retained observation hashes verified before/after and during independent readback. History is a bounded sample, not lifetime completeness.

| Symbol | Deals | Commission nonzero | Fee nonzero | Swap nonzero |
| --- | ---: | ---: | ---: | ---: |
| (nontrade) | 8 | 0 | 0 | 0 |
| BTCUSDm | 33 | 0 | 0 | 0 |
| USOILm | 2 | 0 | 0 | 0 |
| USTECm | 12 | 0 | 0 | 0 |
| XAUUSDm | 76 | 0 | 0 | 0 |

The JSON retains each entry/exit group, observed/missing counts, signed per-lot minimum/median/maximum, and nonzero counts for commission, fee and swap. Zero observations mean observed zero in this sample, never a guaranteed zero schedule. Zero-volume records are excluded from per-lot division.

| Broker symbol | Quotes | Min spread | Median | p90 | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTCUSDm | 169 | 10.00 | 10.00 | 10.00 | 10.0 | 10.00 |
| USTECm | 176 | 1.12 | 1.12 | 1.12 | 1.12 | 1.12 |
| XAUUSDm | 172 | 0.260 | 0.260 | 0.260 | 0.260 | 0.260 |

Decimal ask−bid; midpoint median and nearest-rank percentiles. Distinct retained quote-content samples are not time-weighted, not a backtest spread model, and not a forecast.

## Rounding investigation and deviations

- Initial half-cent assumption failed on BTC (-$0.01 broker versus -$0.00110 unrounded domain). The capture stopped. Separate preserved 84-row-per-symbol probes explained BTC/gold results by rounded monetary legs. Acceptance now requires a documented two-half-unit bound plus propagated binary ULPs and membership in explicit rounding predictions. This is a bounded sampled observation, not a claim about broker internals.
- The first complete calculation capture had no feasible sizing because its synthetic account history omitted UTC midnight. Independent review caught this. Only the Phase 4A.1 fixture was corrected; a regression test and mandatory feasible-policy coverage were added. The preliminary capture and manifest remain preserved; final evidence is a separate file.
- A wider stop was added during fake testing to exercise feasible HR sizing under the frozen gross-notional limit. No strategy optimization or policy edits occurred.
- Account currency_digits is the only native metadata addition. The existing safety guard now explicitly permits the two authorized calculators while retaining forbidden trading calls.

## Evidence and gate

- [Machine-readable report and all matrix rows](reports/mt5_broker_economics_calibration.json)
- [Architecture, exact assumptions and tolerance](docs/PHASE4_A1_BROKER_ECONOMICS.md)
- Final ignored capture: `.local/phase4_a1/calibration-20260922-complete.json`
- Accepted SHA-256 manifest: `.local/phase4_a1/accepted-hashes.json`
- Preliminary and rounding diagnostic files remain in `.local/phase4_a1/`.
- `scripts/verify_phase4_a1_evidence.py` reloads all answers, replays the frozen domain, checks every matrix value and decision identity, compares the tracked presentation, and rechecks PostgreSQL observation hashes/profiles.

Full regression status: PASS. `scripts/verify_phase4_a1.ps1` completed with exit 0.

| Check | Result |
| --- | --- |
| Real DEMO profit calibration | PASS — 144 grid comparisons |
| Real DEMO margin calibration | PASS — 24 grid comparisons, plus 27 accepted candidate checks |
| Frozen Risk Engine cross-validation | PASS — 144 scenarios; 27 accepted / 117 rejected |
| Minimum-lot rejection / feasible sizing | PASS — both policies; all three assets |
| Historical cost classification / spread profiles | PASS — 131 deals / 517 quotes |
| Independent saved-evidence replay | PASS — hashes, all matrix rows and decision identities |
| Read-only invariant | PASS — no broker requests or trading calls |
| Full Python / PostgreSQL suite | PASS — 878 tests, including 123 integration tests; zero failures/errors/skips |
| Frontend | PASS — 61 tests, TypeScript, ESLint, Prettier and production build |
| Ruff / format / strict mypy | PASS — 197 formatted files, 163 typed source files |
| Secret scan | PASS — 255 project files, no findings |
| Phase 2B real datasets | PASS — BTCUSD 36,036; XAUUSD 33,647; USTEC100 23,977 bars |
| Phase 3.3B / 3.3C evidence | PASS — original 12 results, splits, identities and aggregation replay |
| Phase 3.4 / 3.5 / 3.6 / 4A regression | PASS |
| Frozen historical evidence | PASS — all 874 files byte-for-byte unchanged |

Full evidence: `test-results/phase4_a1-full-gate.log`,
`test-results/phase4_a1.xml` and `test-results/phase3_6-frontend.xml`.
The composed historical gate runs the full Python suite twice; both runs passed
878 tests. This is the same suite, not 1,756 distinct tests. The existing Phase
3.3B verifier emits its previously known Pydantic deprecation warning; it passed
without changes to frozen code or evidence.

Additional independent checks: the original Phase 4A journal still has 825 valid
events, its 787 observation hashes and checkpoint validate, and its 131 deal
identities are unchanged. A separate arithmetic readback recomputed raw price
loss, exact buffer/fees, volume lattice and conservative margin for all 27 accepted
candidates. Evidence: `test-results/phase4_a1-prior-journal-readback.json` and
`test-results/phase4_a1-independent-arithmetic.json`.

## Files changed

Modified checkpoint files (2):

- `src/trading_ecosystem/mt5/client.py`
- `tests/mt5/test_boundaries.py`

Added files (13):

- `PHASE4_A1_REPORT.md`
- `docs/PHASE4_A1_BROKER_ECONOMICS.md`
- `reports/mt5_broker_economics_calibration.json`
- `scripts/verify_phase4_a1.ps1`
- `scripts/verify_phase4_a1_evidence.py`
- `src/trading_ecosystem/mt5/calculations.py`
- `src/trading_ecosystem/mt5/calibration.py`
- `src/trading_ecosystem/mt5/calibration_economics.py`
- `src/trading_ecosystem/mt5/calibration_matrix.py`
- `src/trading_ecosystem/mt5/calibration_verify.py`
- `src/trading_ecosystem/mt5/cost_profile.py`
- `tests/integration/test_mt5_calibration.py`
- `tests/mt5/test_calibration.py`

Dependencies added: none. Runtime captures, manifests, diagnostics and test output
remain ignored. Original Phase 4A report/economics evidence is unchanged. No
Phase 4A.1 commit, tag or push.

## Limitations and stop point

Finite current-environment calibration only. Margin representation is a local conservative estimate; future leverage, contract or conversion conditions require new evidence. Commission, fees, swap and executable stop acceptance are not contractually established. The actual account has no free margin. No real-money or automated execution is authorized. No historical research was rerun. No Phase 4B work was started; the next separately reviewed scope is External EA Observer.
