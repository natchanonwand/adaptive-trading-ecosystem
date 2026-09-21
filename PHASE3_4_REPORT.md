# PHASE 3.4 — PORTFOLIO & RISK ENGINE

Status: COMPLETE — full Phase 3.4 verifier exited successfully.
Baseline: phase3.3c-v0.1.0 / 99d3633. Branch: main; existing untracked Phase 3.4A work retained.
qualification_eligible=false. NO BROKER WRITES. NO STRATEGY OPTIMIZATION. NO LIVE TRADING.

| Implementation | Result |
|---|---|
| Portfolio accounting / long and short bid-ask marking | PASS |
| Weighted fills / partial and full close / no accidental reversal | PASS |
| Independent sizing / broker min-max-step lattice | PASS |
| Aggregate open and reserved risk / serial reservations | PASS |
| Margin / gross exposure / count / asset occupancy gates | PASS |
| ACTIVE / PAUSE_ENTRIES / latched HALT_AND_FLATTEN | PASS |
| V0 conservative policy preserved | PASS |
| HR 5% policy isolated; real/unknown accounts rejected | PASS |

| Verification | Result |
|---|---|
| Frozen Phase 1–3.3C regression tests | 503 passed |
| Preserved Phase 3.4A tests | 67 passed |
| New Phase 3.4 tests, including PostgreSQL pipeline | 76 passed |
| Total | 646 passed, zero failures/skips |
| Ruff | PASS |
| Ruff format | PASS — 145 files |
| Strict mypy | PASS — 119 source files |
| Secret scan | PASS — 166 project files, including final report |
| Fresh PostgreSQL migration/journal/pipeline regressions | PASS |
| Phase 2B real datasets | PASS — 36036 BTCUSD / 23977 USTEC100 / 33647 XAUUSD bars |
| Phase 3.3B existing research evidence | PASS — all 12 results, splits, run identity and exact report |
| Phase 3.3C existing portfolio evidence | PASS — four R-space and four synthetic results, replay and report |
| All 874 dataset/research files unchanged | PASS — identical file set and SHA-256 before/after |

Verified research runs: `phase3_3b-e0a03fae2bf50aadd651586b` and
`phase3_3c-a78142064358de1978b2c420`. No historical strategy simulations were rerun.
Full-suite machine-readable evidence: `test-results/phase3_3b.xml` (646 tests).
The earlier Phase 2B gate passed 645 tests before the final lattice edge-case test
was added; the subsequent full Phase 3.3B gate includes that test and all final code.

## New files in this implementation

- docs/PHASE3_4_PORTFOLIO_RISK_ENGINE.md
- PHASE3_4_REPORT.md
- scripts/verify_phase3_4.ps1
- src/trading_ecosystem/portfolio/__init__.py
- src/trading_ecosystem/portfolio/contracts.py
- src/trading_ecosystem/portfolio/fills.py
- src/trading_ecosystem/portfolio/projection.py
- src/trading_ecosystem/risk/__init__.py
- src/trading_ecosystem/risk/contracts.py
- src/trading_ecosystem/risk/engine.py
- tests/phase34/__init__.py
- tests/phase34/fixtures.py
- tests/phase34/test_portfolio.py
- tests/phase34/test_risk.py
- tests/phase34/test_scope.py
- tests/integration/test_phase34_pipeline.py

## Existing working files modified

- tests/accounting/test_scope.py: allow authorized new Phase 3.4 paths when staged;
  a new regression separately checks every file tracked at the frozen tag unchanged.

## Preserved untracked Phase 3.4A files

- scripts/verify_phase3_4a.ps1
- src/trading_ecosystem/accounting/__init__.py
- src/trading_ecosystem/accounting/contracts.py
- src/trading_ecosystem/accounting/performance.py
- src/trading_ecosystem/accounting/projection.py
- tests/accounting/__init__.py
- tests/accounting/test_accounting.py

## Architecture decisions and findings

No shared frozen component was modified, and no historical simulation was regenerated.
The new portfolio package retains strategy/episode attribution and reuses existing
accounting balance/NAV/day kernels through a typed aggregate valuation bridge.
This keeps the prior long-only Phase 3.4A API and all its tests intact.

V0 uses its specified largest volume satisfying all constraints. HR selects the
5%-budget volume and rejects insufficient remaining aggregate/margin/exposure
capacity, preserving the owner's explicit 7% + 5% > 10% rejection requirement.
The other conservative limits remain unchanged for HR. New SHORT support is confined
to monetary accounting and the experimental policy; frozen V0 remains long only.

Tests confirmed that minimum tradable risk USD 1.02 exceeds the USD 0.75 budget on a
USD 300 V0 account, so the trade rejects without changing the stop or rounding up.
Risk status evaluates the closing UTC day before midnight rollover to avoid erasing
a loss breach. Supplied higher reconciled margin/risk totals cannot be understated
by smaller modeled totals. A transient Windows WMI diagnostic appeared during an
early targeted pytest run; later full regression completed successfully.
An extreme-magnitude regression checks that Decimal34 rounding cannot return a
volume off the broker lattice; unrepresentable lattice offsets reject explicitly.

## Limitations and stopping point

Instrument economics are explicit synthetic/validated-input contracts, not proof of
broker D01 validation. Only the supplied linear USD valuation/margin/commission model
is supported. Sampling cannot infer unobserved intraday peaks. Full-history replay
has not been optimized for production throughput. Risk reservations are pure serial
transitions; durable atomic persistence, partial-fill reservation reconciliation,
authenticated human reset, protection coordination and broker execution remain
future work. No engine function reads a database, network, MT5 or wall clock.

Git diff summary: zero tracked baseline changes; 24 untracked Phase 3.4 files
(16 newly created this implementation, 8 retained from Phase 3.4A, including the
one updated scope test). Branch remains main. No commit, tag or push.
STOP after Phase 3.4; Phase 3.5/3.6, monitoring, dashboard and MT5 execution not started.
