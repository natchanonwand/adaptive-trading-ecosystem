# Phase 5C.2C — Portable environment qualification

Status: BLOCKED / ACCOUNT_CONTEXT_FAILURE. One qualification probe completed. Full regression gate PASS.
Environment qualification has NOT succeeded; no environment-ready record or campaign grant was created.

## Baseline and original root cause

Frozen baseline: phase5c-prereg-v0.1.0, 4590de24d566a8c6f103f2f0ba2adc4254f859ab.
HEAD, origin/main and every previous tag remain unchanged. No commit/tag/push.
The original INITIALIZATION_FAILED was an explicit fail-closed guard in adapter.load_environment:
no usable isolated broker/tester profile had been qualified. It was not native proof of an EA defect.
The existing portable adapter creates a fresh profile and copies terminal binaries plus the authorized
project-owned Expert; it deliberately does not copy accounts, authentication stores or credentials.

## One native qualification attempt

Probe ID: `b39c47cb-1a2e-4650-b7a1-a6d813865bcb`.
Kind: ENVIRONMENT_QUALIFICATION, execution strategy PORTABLE_ARTIFACT.
Candidate: b847df2f-2f5b-4941-881a-efaab99300eb.
Campaign: acc5933d-3135-524e-a6af-17ae7f77eb1e.
Canonical EX5: `36e7a042cb8c67eb25ade8a9ce1ce37f0314844842c4ae87e0d84003bb0921a1`.
Source: 4800f441238fd5a0eaff63e7839865770e4af8fcec4f293b6cc40f07a2dcc46f.
Original and staged artifact hashes matched; source unchanged, no rebuild or substitution.
Paths validated with existing absolute-path/symlink/junction checks. Unique runtime cannot overwrite
an earlier probe. Existing Adapter staging and Windows job-owned process execution were reused.

Read-only installed terminal/profile identity and build 6230 were verified. The connected Exness
Technologies Ltd / Exness-MT5Trial14 account was DEMO and matched the previously salted fingerprint.
AutoTrading was disabled; this was not treated as a tester blocker. Installed account verification
is distinct from account availability in the new isolated portable profile.

Probe parameters: XAUUSDm, M5, Model=4 (EVERY_TICK_BASED_ON_REAL_TICKS), inputs exactly
InpFastEmaPeriod=20 and InpSlowEmaPeriod=100, deposit 300 USD, leverage 100, 60-second maximum.
Historical interval: 2026-01-05 to 2026-01-06. This is a separate qualification interval, not an
ExperimentRun or a campaign configuration execution. No campaign reservation was created.

| Lifecycle | Evidence |
| --- | --- |
| Canonical artifact | VERIFIED |
| Portable staging | VERIFIED; SHA equals canonical |
| Native terminal | Build 6230, owned process created and exited |
| Config consumption | Native Startup journal confirms exact tester.ini path |
| Tester initialization | NOT REACHED |
| Exact native blocker | tester not started because the account is not specified |
| Failure boundary | ACCOUNT_CONTEXT_FAILURE in isolated portable profile |
| Expert load / OnInit | UNVERIFIED; no tester child observed |
| Requested real-tick model | Configured Model=4 |
| Native model accepted | UNVERIFIED |
| Full interval real-tick coverage | UNKNOWN |
| Exit | -1000012353 (unsigned 3294954943); not timeout |
| Bootstrap ready | FALSE |

Native process time: 2026-10-13T01:53:56.238190Z to 2026-10-13T01:54:04.833664Z.
MQL5.community authorization failure and an MCP port collision were also logged, but are not used
to infer a trading-account/license denial. The explicit Tester account-missing message supports
the primary classification. The terminal emitted an update-MetaEditor advisory; no compiler was
invoked and the pinned artifact remained unchanged.

Evidence manifest identity: `6c151272b9dfcdc68d2c93bcc4301b7e4699bd18372cdf5b65ceebc8b6917104`.
Evidence is preserved in ignored `.local/phase5_c2c/probe/`; manifest files were independently
rehashed and process termination read back. No retry. No incidental performance was published.
The account-login value stayed in memory; no password or authentication store was read/copied.

## Research preservation and UI

Campaign remains NOT_AUTHORIZED; Workbench START disabled. Existing INITIALIZATION_FAILED
readiness badge remains accurate; exact qualification failure is in this report and probe evidence.
No UI redesign or automatic authorization transition. No qualification success record was created.
Reference campaign execution count 0, budget consumption 0/11, frozen candidate set 9,
Gold Scalper execution count 1, OOS SEALED. All original database rows and prior probe evidence
remain unchanged. BaselineRuns 3, BaselineResults 0, derived publications 1.

## Verification

- Backend: 1551 PASS, including 314 PostgreSQL/integration tests.
- Frontend: 177 PASS (unchanged).
- New qualification tests: 15 PASS; existing adapter/account/campaign regression tests unchanged.
- Ruff, formatting, strict mypy, secret scan: PASS.
- Frontend typecheck/lint/format/build: PASS.
- Isolated migration tests, scope, Git-ignore, lineage, git diff --check: PASS.
- 1,044 frozen and 1,621 historical evidence files byte-identical.
- Phase 5C.2B source/report/runtime snapshot and ten research tables unchanged.
- Full log: `.local/phase5_c2c/full-gate.log`.

Added tests cover exact baseline parameters, invalid bindings, excluded OOS interval, artifact
rejection before launch, unchanged source, safe-path rejection, fail-closed bootstrap interpretation,
model/coverage separation, no synthetic performance and no automatic authorization. Successful
qualification and a READY transition remain unproven because the single permitted probe failed;
no synthetic success test/evidence substitutes for that missing native qualification.

## Files changed

- src/trading_ecosystem/tester/portable_qualification.py
- tests/test_portable_qualification.py
- scripts/verify_phase5_c2c.py
- scripts/verify_phase5_c2c.ps1
- PHASE5_C2C_REPORT.md

## Remaining blocker / strict stop

A verified installed account is not automatically available in a new portable profile. Resolving
this requires a separately reviewed account-context provisioning design under the existing no-
credential-copying rules. No further probe is authorized by this phase; do not retry automatically.
A separate campaign START authorization cannot safely be issued now. No source changes, rebuild,
campaign execution, budget consumption, OOS access, Phase 5C.3, commit, tag or push occurred.
Qualification remains BLOCKED; this is a valid failed probe outcome, not a claim of completion
of the environment-readiness goal. No other scope deviations.
