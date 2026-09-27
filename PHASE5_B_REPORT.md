# Phase 5B — Automated MT5 Strategy Tester Baseline Runner

Date: 2026-09-27. Immediate baseline: `phase5a-v0.1.1` / `e83c41b`.
Original Phase 5A: `phase5a-v0.1.0` / `ec87ad2`, preserved unchanged.

**Tooling: `SOFTWARE_TOOLING_COMPLETE / PASS`.** The final complete gate passed
**1,206 backend tests (including 219 PostgreSQL/integration tests)** and
**96 frontend tests**. Phase 5B adds 82 backend and 14 frontend tests; all previous
tests pass unchanged. Final log: `test-results/phase5_b-release-gate.log`.

**Real acceptance: `BLOCKED_NO_AUTHORIZED_CANDIDATE`.** Read-only inspection of the
actual application database at `2026-09-27T02:07:31.992422+00:00` found 0 projects
and 0 registered authorized candidates. No native MT5 process or external EA was
started. No normalized real baseline result or real run ID exists. Synthetic
fixture metrics are test data only and are not reported as real results.

## Preconditions and preservation

Before implementation, HEAD, `phase5a-v0.1.1`, local `origin/main` and the actual
remote main ref all resolved to `e83c41b3d41704c276f98b0912439d13400eb490`.
The working tree was clean. The unchanged Phase 5A gate passed 1,124 backend
tests and 82 frontend tests before any Phase 5B implementation.

The current scope check preserves 367 unchanged tracked snapshot files; only
three existing Workbench integration files are authorized changes. The original
Phase 5A scope gate also passes without relaxing its explicit checkout proof.
All 1,044 previously preserved evidence files remain byte-for-byte unchanged:
874 historical, 53 Phase 4B, 57 Phase 4C and 60 Phase 4D. The four frozen benchmark
identities and registry hash remain valid. No historical campaign was rerun.

Neither Phase 5A tag was moved, rewritten, amended or recreated. No commit,
tag, push, Phase 5C, optimization, behavior inference or broker trading occurred.

## Implementation

| Area | Delivered behavior |
|---|---|
| Configuration | Persisted immutable UUID configuration, exact project/candidate/EX5 identities, dates, USD deposit, leverage, timeout and input provenance |
| Migration | Independent additive `0001_baselines` lineage; `workbench.baseline_runs` and `workbench.baseline_results`; existing Workbench/core heads unchanged |
| Adapter | Native `/portable` and `/config` orchestration, fresh UUID staging, pinned terminal and registered EX5 hash checks, exact symbol cache, no source-terminal mutation |
| Process | Suspended Windows child assigned to a kill-on-close Job Object, hidden window, minimal environment, bounded timeout, owned descendant termination |
| Concurrency | Local ownership lock, explicit busy response, no automatic retry; interrupted run marked failed with partial evidence preserved |
| Cancellation | Ready/owned active cancellation; completion and cancellation serialized; another server cannot falsely cancel a process it does not own |
| Fidelity | Real-ticks model only; no downgrade; log evidence required and known generated-tick fallback rejected |
| Parser | Deterministic English UTF-8/UTF-16 HTML parsing, numeric/locale checks, trade-count consistency, drawdown/duration validation, unavailable semantics |
| Identity checks | Expert UUID, exact symbol/timeframe/date interval/deposit/leverage; currency/model when exposed; independent saved-report readback |
| Evidence | Ignored immutable run directory, configuration, staged runtime hashes, report, sanitized diagnostics, normalized result and manifest |
| UI/API | Persist/review/confirm/start, saved runs, actual status/elapsed time, cancel, metrics and identities, actionable failures; local same-origin endpoints |

The parser covers deposit; net/gross profit and loss; profit factor; expected
payoff; balance/equity drawdown; trade/win/loss and long/short counts; win rate;
largest/average trade profit/loss; consecutive wins/losses; average/maximum holding
time; and available tester metadata. Missing values are explicitly UNAVAILABLE.
No profit ranking or score is produced.

The existing project record continues to describe onboarding readiness; separate
BaselineRun records are authoritative for execution status. Old Phase 5A server
behavior and tests remain intact, while the normal Workbench entry point starts
the Phase 5B server. Normal users review and execute through the Baseline tab.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Pre-implementation Phase 5A gate | PASS | `test-results/phase5_b-v011-prerequisite-gate.log`; 1,124 backend / 82 frontend |
| Final backend + PostgreSQL regression | PASS | 1,206 tests; 219 integration tests included; no skipped tests |
| Frontend tests/typecheck/lint/format/build | PASS | 96 tests; no fake progress; confirmation/results/failure paths |
| Ruff / format / strict mypy / secret scan | PASS | 314 Python files formatted; 268 strict-mypy source files; 397 files scanned, no secrets |
| Migration upgrade/idempotency and old-head preservation | PASS | Fresh PostgreSQL integration tests |
| Scope, ignored artifacts, binary handling, broker-write/optimization guards | PASS | `verify_phase5_b_scope.py` |
| Frozen evidence and registry | PASS | Unchanged Phase 5A gate; 1,044 evidence files |
| Independent Phase 5B evidence reload | PASS | 0 finalized real run manifests; zero does not establish acceptance |
| Git whitespace and final gate | PASS | `scripts/verify_phase5_b.ps1`, exit 0 |
| Real acceptance | BLOCKED | `BLOCKED_NO_AUTHORIZED_CANDIDATE`; zero EA executions |

The parser fixture is hand-authored synthetic MT5-style HTML. Process ownership
tests execute harmless Python children, never synthetic EX5 bytes. Integration
tests use fresh disposable PostgreSQL databases and a simulated native process
boundary with the actual adapter staging. Native MT5/EA compatibility remains a
separate, unfulfilled acceptance condition.

## Files changed

Existing files modified (3):

- `src/trading_ecosystem/workbench/__main__.py` — start the Phase 5B server.
- `dashboard/src/workbench/Workbench.tsx` — capability-based Baseline panel and onboarding copy.
- `dashboard/src/workbench/api.ts` — optional baseline capability flag.

New files (27):

- `alembic-baseline.ini`
- `migrations/baseline/__init__.py`
- `migrations/baseline/env.py`
- `migrations/baseline/versions/__init__.py`
- `migrations/baseline/versions/0001_baselines.py`
- `src/trading_ecosystem/tester/__init__.py`
- `src/trading_ecosystem/tester/contracts.py`
- `src/trading_ecosystem/tester/inputs.py`
- `src/trading_ecosystem/tester/parser.py`
- `src/trading_ecosystem/tester/process.py`
- `src/trading_ecosystem/tester/adapter.py`
- `src/trading_ecosystem/tester/store.py`
- `src/trading_ecosystem/tester/evidence.py`
- `src/trading_ecosystem/tester/service.py`
- `src/trading_ecosystem/tester/api.py`
- `dashboard/src/workbench/BaselinePanel.tsx`
- `dashboard/tests/baseline.test.tsx`
- `tests/fixtures/phase5b_report.htm`
- `tests/phase5b_helpers.py`
- `tests/test_phase5b.py`
- `tests/integration/test_baseline.py`
- `scripts/verify_phase5_b.ps1`
- `scripts/verify_phase5_b_scope.py`
- `scripts/verify_phase5_b_evidence.py`
- `scripts/phase5_b_acceptance_readiness.py`
- `docs/PHASE5_B_AUTOMATED_BASELINE.md`
- `PHASE5_B_REPORT.md`

Generated ignored outputs: `.local/phase5_b/baseline.json`, timestamped
acceptance-readiness JSON, local web-service PID/log/lock files, test logs/JUnit
under `test-results`, and the built `dashboard/dist` assets. No EX5, native tester report or real run directory was
created for acceptance. Prior frozen evidence was read only.

## Limitations and deviations

- No authorized candidate is registered; `REAL_EXTERNAL_EA_BASELINE_COMPLETE`
  is not established. No real profit, drawdown or trade statistics are available.
- `.local/phase5_b/environment.json` has not been provisioned. An operator must
  pin the project's installed terminal and appropriate already-cached symbol data
  before future authorized testing. No credentials or activation material are copied.
- The isolated offline portable adapter has not been qualified against a real EA.
  Native initialization, broker cache layout, additional dependencies, activation,
  DLL-dependent EAs or unsupported report locales may block/fail. There is no
  download, authentication, licensing workaround or lower-fidelity fallback.
- Current real-tick evidence recognition is conservative and English-text based.
  Unknown log formats block completion. Build configuration is operator-declared;
  absent native report build fields remain UNAVAILABLE.
- Staging is capped at 2 GiB and has a checked 120-second loop deadline; individual
  OS copy calls are not preempted. Job Objects control process ownership, not
  arbitrary hostile-binary filesystem/network behavior. Artifacts must be trusted.
- The saved-run list is bounded to 100 per project. No distributed queue, tuning,
  automatic input extraction, or behavior fingerprinting is implemented.
- Deliberate implementation choices: additive migration version table preserves
  the old migration head; isolated portable staging preserves installed terminals.
  Credential-like reports are rejected/redacted with original hash retained rather
  than keeping private raw content. These choices do not expand authorized scope.
- No unauthorized scope deviation. The real acceptance exception is used exactly
  as specified because no authorized candidate is registered.

Operational details: [Phase 5B documentation](docs/PHASE5_B_AUTOMATED_BASELINE.md).

Local application migration was applied and read back: core `0001_journal`,
Workbench `0001_projects`, baseline `0001_baselines`; 0 baseline runs and 0
baseline results. The local Workbench is running at
`http://127.0.0.1:8785/workbench`; HTTP page and baseline-list API smoke checks
passed with zero projects/runs. Starting this web service did not start MT5.
