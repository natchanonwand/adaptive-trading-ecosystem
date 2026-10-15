# Phase 5C.2D — Authenticated research account context qualification

Status: NATIVE ENVIRONMENT QUALIFICATION PASS. Full regression gate PASS.
Campaign remains NOT_AUTHORIZED / START disabled. This phase did not enable the campaign adapter.

## Baseline and amended contract

Frozen baseline phase5c-envprobe-v0.1.0 at 6477b0a52c3a9ec183cfbfae51628616ab189083.
Prior ownership-blocked and closed-session-blocked dry-runs remain preserved. The user amended the
contract to distinguish OFFLINE persisted-context readiness from RUNTIME account acceptance.
No live SDK/session call is used in the revised offline dry-run. Account-store existence and size
are checked only; its bytes are not read, hashed, decrypted, parsed, copied or exported.

Artifact strategy: PORTABLE_ARTIFACT. Account-context strategy: AUTHENTICATED_PROFILE_REFERENCE.
Terminal mode: MAIN_MODE, no /portable switch. Use the original pinned installation and data root.
The generated tester config retains the known Phase 5B server selector and lets MT5 resolve its
saved last-account association. No Login was guessed/recovered and no Password was supplied.
This establishes only PERSISTED_ACCOUNT_CONTEXT_READY_FOR_RUNTIME_PROBE before native launch.

Binding identity: `c4b31d3f5ea7decd18e0966c19312797ccc6c4050a91ad1d52989291363e29e2`.
Canonical EX5: 36e7a042cb8c67eb25ade8a9ce1ce37f0314844842c4ae87e0d84003bb0921a1.
Source SHA: 4800f441238fd5a0eaff63e7839865770e4af8fcec4f293b6cc40f07a2dcc46f.
Both remained unchanged. Source was not compiled or altered.
Binding includes canonical artifact/candidate, pinned executable/profile/build, prior safe salted
account fingerprint, DEMO/company/server, research purpose and persisted-readiness state. Its
identity excludes PID, observation timestamps and ephemeral paths.

## Dry-run and one probe

Ownership clear; previous PID 576 absent. Build 6230 and target data root verified.
Account store present in the original profile; prior safe DEMO attestation verified against its
immutable file manifest. Staging uses unique UUID paths and exclusive creation, absolute path
validation and symlink/junction rejection. Process ownership is guarded by an exclusive research
lock and fresh process check; no unrelated terminal was stopped. No credential persistence.

Probe ID: `1ca70ace-e322-4549-beee-d73d2856d8ff`.
Phase 5C.2D native qualification probes consumed: exactly 1. No retry.
Kind: ENVIRONMENT_QUALIFICATION, not ExperimentRun or BaselineRun.
Candidate: b847df2f-2f5b-4941-881a-efaab99300eb.
Campaign: acc5933d-3135-524e-a6af-17ae7f77eb1e.
XAUUSDm / M5 / Model=4 EVERY_TICK_BASED_ON_REAL_TICKS.
Inputs: InpFastEmaPeriod=20; InpSlowEmaPeriod=100.
Qualification interval: 2026-01-05 to 2026-01-06, maximum 60 seconds, deposit 300 USD, leverage100.
No performance result entered experiment objective/selection; no result parser or DB insert used.

Native lifetime: 2026-10-14T13:27:29.928663Z to 2026-10-14T13:28:06.464361Z.
Terminal exit 0; owned tester exit 0; no timeout. All observed descendants ended.

| State | Evidence |
| --- | --- |
| PROCESS_STARTED | Pinned terminal identity verified |
| CONFIG_ACCEPTED | Exact qualification config path in native Startup journal |
| ACCOUNT_CONTEXT_ACCEPTED | Runtime read-only SDK: DEMO, Exness Technologies Ltd, Exness-MT5Trial14, prior salted fingerprint matched; native authorization corroborated |
| TESTER_SUBSYSTEM_STARTING | Owned metatester64.exe child and verified executable hash |
| TESTER_INITIALIZED | Native tester successfully initialized and executed exact UUID Expert |
| EXPERT_LOADED | Exact UUID Expert file loaded in new agent log |
| EXPERT_ONINIT_SUCCEEDED | Exact Expert's test started and completed successfully in the same ordered journal, without initialization rejection |
| BOOTSTRAP_READY | Runtime account, exact Expert completion, tester ancestry and cleanup verified |
| REQUESTED_REAL_TICK_MODE_ACCEPTED | Model4 configured; native log generating based on real ticks |
| FULL_INTERVAL_REAL_TICK_COVERAGE_VERIFIED | NOT CLAIMED; remains UNKNOWN for DEV/VALIDATION splits |

## Immutable assessment derivation

Original manifest: `d62b7de0d7cd2becd77b592f9896fd461ad580142332e92a4b9a8dbf516ae246`.
The first automatic assessment recorded BOOTSTRAP_UNVERIFIED because the reused handshake parser
required an ordered startup banner omitted from the appended log segment. It already observed
runtime account acceptance, loaded Expert, successful OnInit/test and exit0. The original assessment
and raw evidence were not rewritten. A narrow corrected interpreter requires an owned tester,
config acceptance and the exact UUID Expert's ordered completion within the same fresh log.
No second execution was used to resolve this parser issue.

Derived qualification identity: `4275f17ec198aee72508675677bf93d87f096b262b9b15aa71efc82afc8fabcc`.
Derived state: EXECUTION_ENVIRONMENT_READY.
Stored at `.local/phase5_c2d/qualification.json`, linked to original evidence and immutable binding.
Readback recomputes the manifest and derived identity before exposing the qualification.

## Profile safety and observed limitation

The lifecycle staged only UUID-owned EX5 and .set plus a private generated INI. Those files and
UUID reports/graphs were removed after the run. No account database was copied or edited by the
adapter. All pre-existing Expert binaries, including Gold Scalper, were byte-identical afterward.
Native MT5-managed logs/cache/profile behavior is distinct from adapter-owned file mutation.

IMPORTANT: main-mode startup also restored an existing chart Expert, Smart Hedge Pro, according
to the terminal log. Config had Experts Enabled=0 and AllowLiveTrading=0; the runtime SDK account
check required trade_allowed=False. The observed native synchronization reported zero positions
and orders. This does not establish that no chart initialization code ran. No deliberate launch
of that chart Expert was performed, but it is an incidental profile-restoration side effect and
must be reviewed before any future campaign uses this profile. Do not interpret this probe as
qualification of arbitrary interactive profile contents or authorization for broker execution.

## Workbench and campaign separation

A narrow read-only qualification display exposes account acceptance, environment READY and its
identity independently from campaign authorization. No campaign grant was created. The existing
campaign loader still reports its legacy INITIALIZATION_FAILED prerequisite because its blank
portable execution adapter was not silently replaced by this qualification-only main-mode wrapper.
Thus START remains disabled and no execution path was enabled. Environment qualification evidence
can be reviewed for a subsequent explicit authorization/integration decision; this is not a claim
that the existing campaign runner can already execute through the new context.

Research DB unchanged: 9 frozen candidates, campaign identity unchanged, campaign executions0,
budget0/11, Gold Scalper executions1, BaselineRuns3, BaselineResults0, derived publications1.
LOCKED_OOS remains SEALED; no DEV/VALIDATION/OOS execution or performance interpretation.

## Verification

Backend 1568 PASS, including 314 PostgreSQL/integration tests.
Frontend178 PASS. New tests: 17 backend, 1 frontend.
Ruff / Python format / strict mypy / secret scan PASS.
Frontend typecheck/lint/format/build PASS. Isolated migrations, scope, Git-ignore, registry,
lineage and git diff --check PASS. Frozen evidence1044 and historical evidence1621 byte-identical.
Phase5C.2C diagnostic evidence and all research database rows unchanged.
Full gate log: `.local/phase5_c2d/full-gate.log`.

Tests exercise offline metadata without store reads, no SDK offline, ownership blocking, absent
store, deterministic non-secret binding, wrong account/profile/server/DEMO rejection, runtime
fingerprint matching, generic failures not proving credential requirements, ordered same-source
Expert evidence, no synthetic performance, and environment READY not granting Start.
Existing staging/account/lifecycle/runner regression tests remain unchanged.

## Files changed

- src/trading_ecosystem/tester/account_context_qualification.py
- src/trading_ecosystem/experiments/authorization.py
- tests/test_account_context_qualification.py
- dashboard/src/workbench/CampaignAuthorization.tsx
- dashboard/tests/environment-qualification.test.tsx
- scripts/verify_phase5_c2d.py
- scripts/verify_phase5_c2d.ps1
- PHASE5_C2D_REPORT.md

## Stop and deviations

No campaign START authorization, campaign execution, canonical rebuild, Gold Scalper execution,
Phase5C.3, commit, tag or push. Native probe consumed once only. A proof-path programming error
was fixed before native launch; all path checks retained. Original handshake interpretation was
reconciled offline with provenance. Incidental restoration of the unrelated chart Expert and the
remaining campaign-adapter integration limitation are explicitly recorded above. No further probe
or automatic profile cleanup was performed.
