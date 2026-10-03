# Phase 5B.1E — Research account binding and native account-context validation

Baseline: `phase5b-tooling-v0.1.7`, commit
`3f88a030d7f6b67d47f7a3fea01b490a8ca0bde5`. Prior tags remain immutable.

## Status

Phase 5B.1E: **IMPLEMENTATION COMPLETE / PASS**.
Native result: **BOOTSTRAP_READY**. Complete Phase 5B regression gate: **PASS**.
Exactly one new environment probe was executed; no candidate or BaselineRun was created.

## Account context and safety

Fresh SDK observation confirmed the pinned running terminal executable, build 6230,
and data root/profile. Company: Exness Technologies Ltd. Server: Exness-MT5Trial14.
Account trade mode: DEMO. Connected: true. AutoTrading: disabled.

Persisted fields: account_binding_id, terminal_binding_id, company, server,
environment_classification, account_fingerprint, verified_at, discovery_source.
The native login stays in memory except for an access-limited, ignored, probe-scoped
INI, which is deleted in finally. No passwords, investor passwords, tokens, or
credential database contents were read, copied, or persisted by this implementation.
SDK discovery imports through the existing approved SDK loader and exposes no broker-write API.

The documented `[Common] Login` field asks the existing terminal/profile to reuse its
own authentication context. No credential store was copied to an isolated profile.
The verified operator session was closed gracefully before launching the same installed
executable with the same data root and a temporary startup configuration. Experts and
live trading remained disabled in that configuration; only the fixed tester Expert was staged.

Reference: [MetaTrader platform startup configuration](https://www.metatrader5.com/en/terminal/help/start_advanced/start).

## Native evidence

Probe ID: `8d32eafd-ea25-4fd5-852e-ac0e548bda97`.
Pre-registered maximum launches: 1. Observation bound: 60 seconds, unchanged.
Fixed source/compiler contract retained; source and generated EX5 identities recorded
under ignored `.local/phase5_b1e/probe/`.

| Observation | Result |
| --- | --- |
| PROCESS_STARTED | Verified terminal PID 13652; build 6230 |
| CONFIG_ACCEPTED | Exact startup-config path observed in native terminal journal |
| PROBE_EXPERT_LOADED | Exact UUID Expert component in owned agent journal |
| PROBE_INIT_SUCCEEDED | PHASE5B_PROBE_INIT_OK |
| FIRST_TICK_OBSERVED | PHASE5B_PROBE_FIRST_TICK |
| TESTER_INITIALIZED | Corroborated by verified tester child PID 22600 and Expert markers |
| Normal stop | PHASE5B_PROBE_DEINIT:1, TesterStop, native exit 0 |
| Cleanup | All observed process descendants ended; temporary INI and staged Expert removed |
| Final readiness | BOOTSTRAP_READY |

Terminal lifetime: 2026-10-02 16:56:24.630896 through 16:56:48.377850 UTC.
Native agent OnInit: 23:56:36.358 local; first tick/deinit: 23:56:43.418 local.
Simulated first tick: 2026-01-01 23:05:00. Native journal reports one tick and one bar,
with TesterStop at 0% of the testing interval.

XAUUSDm/M5 initialized using EVERY_TICK_BASED_ON_REAL_TICKS (Model=4).
This establishes real-tick bootstrap only; full 2026-01-01 to 2026-06-30 coverage remains
UNKNOWN. No profitability, candidate license, or candidate compatibility conclusion follows.

Only appended native log data was copied, with the session login replaced and sensitive
lines redacted. Delayed flush can include older journal lines; qualification requires the
new UUID Expert's ordered markers and verified process ancestry, not generic old messages.
Existing MT5-managed profile logs/caches remain native-owned; historical project probe evidence
was never rewritten. Five native HTML/PNG outputs belonging solely to this probe UUID were
removed without importing their contents into project evidence.

## Changes and validation

- src/trading_ecosystem/tester/research_account.py: strict read-only DEMO binding.
- src/trading_ecosystem/tester/account_probe.py: same-profile one-shot diagnostic and cleanup.
- src/trading_ecosystem/tester/checkpoint.py: immutable v0.1.7 lineage pin.
- scripts/verify_phase5_b_scope.py: narrow Phase 5B.1E change allowlist.
- tests/test_phase5b_research_account.py: identity, fail-closed, disclosure, cleanup, one-shot tests.
- PHASE5_B1E_REPORT.md: this report.

Tests cover missing/unknown/live account, broker/server/profile/build mismatch, safe identity,
no sensitive binding fields, ephemeral materialization, failure cleanup, immutable configuration,
no candidate/result creation, fixed timeout, duplicate invocation rejection, and native report cleanup.
Existing no-trade marker, account-blocker, source-safety and compilation tests remain unchanged.

Independent readback verified all 13 new probe files against their SHA-256 manifest and
all 1,462 prior probe/run evidence files byte-for-byte. Reclassification using only native
journal timestamps within the verified process window independently returned BOOTSTRAP_READY.
Historical project, declarations, BaselineConfiguration and both failed BaselineRuns matched
the pre-probe snapshots exactly. All 19 existing tag objects and HEAD remained unchanged.

The new test module adds 22 tests. Final log: `test-results/phase5_b1e-final-gate.log`.

| Final verification | Result |
| --- | --- |
| Backend regression | PASS — 1,312 tests |
| PostgreSQL/integration and migrations | PASS — 231 tests included in backend total |
| Frontend regression | PASS — 100 tests across 11 files |
| Ruff / Ruff format | PASS |
| Strict mypy | PASS — 283 source files |
| Secret scan | PASS — 423 project files |
| Frontend typecheck / lint / format / production build | PASS |
| Scope / Git-ignore / frozen registry / lineage | PASS |
| Frozen evidence | PASS — 1,044 files byte-identical |
| Historical probe/run evidence | PASS — 1,462 files byte-identical; 2 run manifests verified |
| New probe independent readback | PASS — 13 files, one launch, fresh-window markers |
| Project / BaselineConfiguration / BaselineRuns | Unchanged |
| git diff --check | PASS |

No remaining account-context/bootstrap blocker was observed for this fixed no-trade probe.
Candidate execution and complete historical tick coverage remain unqualified.

## Limits and deviations

Gold Scalper was not retried and remains unauthorized for an automatic retry by this phase.
The production candidate adapter remains fail-closed: environment bootstrap readiness does not
enable candidate execution. Workbench project/candidate declarations were not changed.
No full historical coverage claim, optimization, forward trading, Phase 5C, commit, tag, or push.

The first preservation read could not reach the stopped Workbench. The existing PostgreSQL
sandbox and Workbench were restarted, then the old project/config/run snapshots matched before
the native probe. The native probe was not retried. A synthetic secret-test value was explicitly
allowlisted; scanner behavior was not weakened. The first full gate stopped after backend PASS
because formatting moved the synthetic password's allowlist comment to the adjacent token line.
The comment was corrected on the fixture line and the complete gate was rerun.
Native report cleanup was completed after the
one probe and incorporated into the implementation; the original probe evidence was preserved.
