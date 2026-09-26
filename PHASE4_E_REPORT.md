# PHASE 4E — REAL EXTERNAL EA QUALIFICATION

PHASE 4E TOOLING: **COMPLETE / PASS**.

REAL EXTERNAL EA CAMPAIGN: **BLOCKED — EA NOT PROVIDED / NOT ATTESTED**.
Installed filenames do not establish a selected, licensed and exclusively bound
candidate. No real campaign, feature dataset or behavioral conclusion was fabricated.

The complete `scripts/verify_phase4_e.ps1` gate passed with exit code 0.
Final evidence: `test-results/phase4_e-complete-gate-v2.log` and
`test-results/phase4_e.xml`. All 1,074 Python tests passed, including 159
PostgreSQL integration tests, with zero failures, errors or skips.

## Baseline and actual inspection

Phase 4D was reviewed and frozen in local commit `4ce8a06`
(`feat: add deterministic behavioral research engine`). No tag or push.
Phase 4E changes are separate and uncommitted.

Read-only prerequisite inspection at 2026-09-25T00:01:06.366704+00:00 found MT5
connected, terminal build 6182, Exness Technologies Ltd / Exness-MT5Trial14,
USD DEMO account. Algo Trading was disabled. PostgreSQL was reachable.
EA filenames were present, but no candidate, license attestation or exclusive
chart binding was supplied. No binaries/license contents were read. There were
zero open positions/orders and 31 deals in the preceding 24 hours, all magic 0.
These are prerequisite observations, not a qualification campaign dataset.
No EA or terminal setting was changed. Service health at campaign start has
not been established because no campaign was started.

## Qualification state

| Item | Result |
|---|---|
| Tooling | COMPLETE / PASS |
| EA candidate / version / symbols / chart binding | NOT PROVIDED / NOT ATTESTED |
| Broker / environment at inspection | Exness Technologies Ltd / DEMO |
| Real campaign / ID | BLOCKED — EA NOT PROVIDED; no campaign ID |
| Uptime / restarts / disconnects | NOT COLLECTED; real restart NOT TESTED |
| Raw frames / lifecycle events / episodes / completed episodes | NOT COLLECTED |
| Attribution / unknown-source campaign observations | NOT COLLECTED |
| M1 / M5 / M15 / M30 / H1 / H4 coverage | NOT COLLECTED for every timeframe |
| Phase 4B real replay | NOT RUN |
| Phase 4C real features | NOT RUN |
| Phase 4D real research | NOT RUN |
| Data sufficiency | NOT EVALUATED |
| Behavior fingerprint | NOT GENERATED |
| Hypotheses / supported / insufficient | N/A — no real research run |
| Read-only / DEMO guards / IP boundary | PASS: software guards/audit; no real campaign or execution performed |
| Python / PostgreSQL | PASS: 1,074 tests, including 159 integration; zero skipped |
| Phase 4E targeted | PASS: 48 tests, including 3 PostgreSQL integration |
| Frontend tests / build | PASS: 75 tests; production build passed |
| Ruff / format / strict mypy | PASS: 278 formatted files, 236 typed files |
| Secret scan | PASS: 348 project files; no findings |
| Regression evidence chain / complete gate | PASS: Phase 2B through Phase 4D; full gate exit 0 |
| Existing evidence | PASS: all 1,044 files byte-for-byte unchanged |
| REAL EA RESEARCH QUALIFICATION | BLOCKED |

## Implementation and limitations

Bounded foreground campaign identity, license/binding/settings provenance,
health gate, per-poll account protection, immutable journal, controlled observer
restart, explicit fault statuses, reconciliation and offline double rebuild
were added only under Phase 4E paths. Frozen Phase 4D policy and all prior engines
remain unchanged. See `docs/PHASE4_E_REAL_EA_QUALIFICATION.md` for commands,
measurement boundaries, history attribution and the immutable evidence layout.
Phase 4E also refuses qualification of an episode mixing candidate and
manual/unknown attribution before feature generation, because the frozen
research loader selects whole episodes. A PostgreSQL regression assertion
covers this boundary without changing the frozen loader.

Software fixtures test failure handling and PostgreSQL compatibility; they do
not establish real-EA operation, licensing, attribution or native restart success.
Installed filenames alone cannot select or license an EA. User-provided metadata
and an attested binding period covering history are still required. Memory is
Python allocations; brief between-poll outages cannot be measured. Settings
stability requires operator attestation. Interrupted campaigns are retained
without automatic resume. Hashes are not independent provenance signatures.

No background/non-entry denominator was added. Future entry data describes
`P(context | observed entry)`, not `P(entry | context)`. No real fingerprint,
cost conclusion, grid/martingale label or strategy conclusion is established.
Actual latency/events/hour cannot yet be compared with the Phase 4C benchmark.

Optional campaign UI/background sampling were deferred to keep scope bounded.
The final gate composes the existing Phase 4D checks without its readiness
collector, because that collector rewrites preserved Phase 4D evidence.
No tests or thresholds were weakened. No Phase 4E commit/tag/push/publication,
GPT call, strategy synthesis or execution gateway was performed.

The first complete-gate attempt passed 1,074 tests and Phase 2B real dataset
readback, then its next full-suite invocation ended with 1,060 passes and 14
monitoring-migration setup errors. A Windows WMI `0x8007000e` message also
appeared; the precise cause of the migration subprocess failure was not proven.
All 14 affected tests subsequently passed on a new disposable database without
code/migration changes (`test-results/phase4_e-migration-recheck.log`). The failed
attempt remains in `test-results/phase4_e-complete-gate.log`; the fresh full
attempt is recorded separately in `test-results/phase4_e-complete-gate-v2.log`.
That fresh complete attempt passed both full-suite invocations (1,074 tests each),
all quality checks and every required evidence verifier. Counts above describe
unique tests, not the sum of repeated invocations. No setup errors recurred.

## Final regression evidence

| Check | Result |
|---|---|
| Phase 2B real datasets | PASS: BTCUSD 36,036; USTEC100 23,977; XAUUSD 33,647 bars |
| Phase 3.2 registry / Phase 3.3B results | PASS: exact 12 finals, retained partial pairs, identities and split boundaries |
| Phase 3.3C | PASS: four R-space and four synthetic results; replay/report verified |
| Phase 3.4 / 3.5 / 3.6 | PASS: full regression and preserved source checks |
| Phase 4A / 4A.1 | PASS: 144 profit rows, 24 margin rows, 144 risk scenarios, 131 retained unique deals |
| Phase 4B | PASS: 39 targeted tests; existing synthetic exports, hashes and replay |
| Phase 4C | PASS: 45 targeted tests; canonical rebuild, source hashes and leakage checks |
| Phase 4D | PASS: 64 targeted tests; research artifacts/comparison independently rebuilt |
| Historical datasets/research | 874 files unchanged, including retained failed ingestion evidence |
| Phase 4B / 4C / 4D evidence | 53 / 57 / 60 files unchanged |

Prior synthetic qualifications remain synthetic. These regression passes do not
establish real external EA qualification. The only baseline checkpoint created
was the authorized Phase 4D local commit; Phase 4E remains uncommitted for review.

## Reviewable files

All 16 Phase 4E files are new; no tracked Phase 4D file was modified.

| Files | Purpose |
|---|---|
| `src/trading_ecosystem/campaigns/__init__.py` | Package |
| `src/trading_ecosystem/campaigns/__main__.py` | Foreground CLI and local evidence namespace |
| `src/trading_ecosystem/campaigns/contracts.py` | Immutable identity and attested metadata |
| `src/trading_ecosystem/campaigns/health.py` | Read-only start/continuity gates |
| `src/trading_ecosystem/campaigns/journal.py` | Append-only configuration-bound journal |
| `src/trading_ecosystem/campaigns/runtime.py` | Bounded observer controller and fault handling |
| `src/trading_ecosystem/campaigns/diagnostics.py` | Coverage, attribution and observed costs |
| `src/trading_ecosystem/campaigns/finalize.py` | Freeze, double rebuild and independent validation |
| `tests/campaigns/__init__.py` | Test package |
| `tests/campaigns/test_campaigns.py` | Metadata, identity, health and integrity tests |
| `tests/campaigns/test_runtime.py` | Controller fault/restart tests |
| `tests/integration/test_campaigns.py` | PostgreSQL recovery, counts and diagnostics |
| `scripts/verify_phase4_e.ps1` | Complete quality and regression gate |
| `scripts/verify_phase4_e_evidence.py` | Prior evidence preservation and campaign validation |
| `docs/PHASE4_E_REAL_EA_QUALIFICATION.md` | Operating contract and limitations |
| `PHASE4_E_REPORT.md` | This report |

Ignored local prerequisites remain in `.local/phase4_e/prerequisite-inspection.json`
and `.local/phase4_e/preserved-evidence.json`; they are not real campaign outputs.
Software test artifacts are temporary and never published as real evidence.
