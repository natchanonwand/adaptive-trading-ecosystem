# Phase 5C.2E — Execution path and profile isolation assessment

Status: BLOCKED_PROFILE_ISOLATION_UNAVAILABLE (build-specific isolation proof unavailable).
This is a prerequisite stop, not an implementation PASS or evidence that MT5 cannot support isolation.

## Verified baseline

HEAD and origin/main: 54b54ececbb039e19dc02d3627c97b2bb5ab5fd0.
phase5c-envready-v0.1.0 resolves to that exact commit. Working tree was clean before assessment.
The Phase 5C.2D post-freeze verifier passed again, including previous tags, research database,
1,044 frozen evidence files, 1,621 historical files and previous qualification evidence.

Environment qualification identity:
4275f17ec198aee72508675677bf93d87f096b262b9b15aa71efc82afc8fabcc
Account-context binding identity:
c4b31d3f5ea7decd18e0966c19312797ccc6c4050a91ad1d52989291363e29e2
Probe: 1ca70ace-e322-4549-beee-d73d2856d8ff; count unchanged at one.
Canonical EX5: 36e7a042cb8c67eb25ade8a9ce1ce37f0314844842c4ae87e0d84003bb0921a1.

## Offline isolation inspection

The pinned data root contains four chart profiles: British Pound, Default, Euro and Market Overview.
Read-only chart-content inspection found an Expert section and Smart Hedge reference in
Default/chart11.chr. No project-owned research chart workspace was present.
The other inspected profiles had no literal Expert section detected. This static check does not
establish runtime isolation or prove a future launch will select those profiles.
No chart contents, Expert settings, account stores or credentials were persisted in this report.

Official MT5 startup documentation supports /profile:<name> for a pre-created chart profile,
and warns that an invalid profile selection falls back to defaults:
https://www.metatrader5.com/en/terminal/help/start_advanced/start

That generic documentation is not installed-build-6230 qualification evidence. Searching the
existing source, tests, documentation and preserved Phase 5C.2C/2D and Phase 5B.1E qualification
materials found no /profile: selection, ProfileLast setting or research workspace isolation proof.
The successful frozen main-mode probe instead records incidental Smart Hedge Pro restoration.
The current adapter leaves chart-profile selection unspecified; Experts Enabled=0 is insufficient.

## Stop rationale

The authorization requires behavior verified against installed build 6230, no unrelated Expert
side effects, and a non-native dry-run only. Existing evidence does not establish that a dedicated
research workspace is selected without fallback to Default. Neither an empty folder nor a new
launch-plan string would prove RESEARCH_WORKSPACE_SELECTED or UNRELATED_EXPERTS_ABSENT.

Therefore stop at BLOCKED_PROFILE_ISOLATION_UNAVAILABLE, specifically missing build-specific
profile-selection/isolation evidence. No native validation was attempted and no unrelated user
profile was modified. A separately authorized isolation validation, or existing independently
verifiable build-6230 isolation evidence, is needed before this prerequisite can be qualified.
Do not treat this report as authorization to launch such a validation.

## Implementation and dry-run status

Existing BaselineBoundary -> Phase 5B Service remains unchanged. The legacy portable environment
loader still fails closed. MAIN_MODE campaign routing was not enabled before isolation could be
qualified. No duplicate engine, workspace identity or successful dry-run identity was fabricated.
No configuration preview, ExperimentRun, BaselineRun or budget reservation was created.
Environment remains READY; research workspace and campaign path remain BLOCKED.
Campaign remains NOT_AUTHORIZED, START disabled, executions0, budget0/11, OOS sealed.
Gold Scalper execution count remains1. Canonical source/artifact unchanged and not rebuilt.

Only this report was added. No tests/code/UI were changed. Browser review and a fresh full gate
were not run because the explicit isolation prerequisite requires STOP. Prior gate results
(1568 backend including314 integration;178 frontend) are historical, not a new 5C.2E gate.
Phase 5C.2E is incomplete; final START authorization cannot be issued on this assessment.
No commit, tag, push, campaign execution or native probe occurred. No scope deviations.


## Authorized profile isolation validation continuation

The subsequent explicit authorization permitted one terminal-only profile validation.
Current status supersedes the earlier prerequisite status:
BLOCKED_PROFILE_SELECTION_UNVERIFIED.

Discovered profiles: British Pound (4 charts), Default (13), Euro (4), Market Overview (4).
Static scans inspected chart metadata for Expert/script sections, Smart Hedge Pro, custom-code
references and .ex5/.mq5 references. Default/chart11.chr was contaminated; the other three profiles
had no such detected attachment. Euro was selected as an existing simple four-chart profile with
an exact unambiguous name. Existing built-in indicator sections were present; no custom-code
reference was detected. No profile internals or Expert binaries were edited or copied.
Static path/name/root and symlink/junction checks passed. File SHA-256 inventory was captured
in the ignored preregistration. No terminal/tester owned the context before launch.

Exactly one PROFILE_ISOLATION_VALIDATION launch occurred:
8ad3cb60-2af6-4667-87ff-deec7ab1eaa0.
Evidence manifest identity:
7f00eae0ad8020c535384c069dc3b931338f580b56f77b0c4cf1ad048e0bbd7c.
Evidence root: .local/phase5_c2e/profile-isolation-validation.
The helper reused the existing owned-process job, account discovery, log capture and manifest
mechanisms. MAIN_MODE used /profile:Euro and an isolated non-secret startup INI. No /portable,
Login, Password or [Tester] section was supplied. No credential database was accessed/copied.

Native lifetime: 2026-10-15T15:41:09.248333Z to 2026-10-15T15:41:34.900661Z.
The bounded observation window was intentionally cancelled through the owned job after about
25 seconds; this was not a natural successful terminal completion or an execution timeout.
All observed descendants ended. Tester processes observed:0. No new tester log content observed.
The read-only SDK verified pinned build/data context, DEMO, Exness Technologies Ltd,
Exness-MT5Trial14 and the previously qualified salted account fingerprint.
Default profile's entire pre-launch file inventory remained byte-identical.

The fresh journal records startup-config consumption, build6230 and the expected MAIN_MODE data
root. It does NOT identify the active chart profile or chart files loaded from Euro. Neither the
command-line argument nor successful account initialization proves profile selection. No fresh
Expert load/initialization records, including Smart Hedge Pro, were observed; absence alone does
not prove isolation or exclude fallback. Therefore RESEARCH_PROFILE_SELECTED_POSITIVELY and
PROFILE_SELECTION_NO_FALLBACK_VERIFIED remain unverified. No ResearchWorkspaceIdentity issued.

Per the explicit stop rule, no second launch, adapter integration, campaign configuration preview
or campaign dry-run followed. Campaign prerequisite readiness remains BLOCKED; NOT_AUTHORIZED,
START disabled, executions0, budget0/11, OOS sealed. Gold Scalper count remains1.

Files changed: this report only in the tracked scope; ignored helper and additive runtime evidence
were created under .local/phase5_c2e. No production/test implementation changes occurred, so the
conditional full implementation gate was not run. Existing evidence/research-state preservation
and git diff checks were rerun. The original native qualification probe and historical evidence
remain separate and immutable. Final START authorization cannot yet be reviewed as ready.
No scope deviations; the sole allowed isolation validation launch is consumed. No automatic retry.

## Terminal-owned active-profile attestation continuation

A separate authorization allowed one new validation using terminal-owned current-profile readback.
New launch: 0ca6591d-b402-4e75-9cf2-5ababdfe36d3. Requested profile: Euro.
Previous launch/evidence remains preserved. Total isolation launches across both authorizations:2;
this authorization consumed exactly1. No campaign or Strategy Tester was configured.

Result: BLOCKED_PROFILE_SELECTION_UNVERIFIED.
Terminal-owned source: expected pinned data root's config/common.ini, not the custom launch INI.
Pre-launch ProfileLast: Default. Post-launch ProfileLast: Default.
Pre/post SHA-256 (identical):
3abea4ce7100b46d671ad6c3b4b69a18d66fd26a71d080700e51aaf97778da56.
Readback/native evidence manifest identity:
c751b790285630c0a55a31a335c8145408806db0ef74aa55e9f6642e974cfbde.
Independent manifest hash readback passed. No configuration secrets or credential-store contents
were persisted; only requested ProfileLast and source identity/hash were retained.

Deviation: the ignored helper issued a controlled CloseMainWindow request, accepted for its owned
PID20404. A later poll attempted to write the same exclusive controlled-close evidence file again,
raising FileExistsError. The existing process wrapper's finally block closed its owned job.
No terminal/tester remained after cleanup. A completed graceful native shutdown is NOT established.
Account-context observations held in process memory were not persisted before the exception;
therefore account-context verification for this new launch is UNVERIFIED in durable evidence.
Do not substitute the previous launch's account verification for this launch.

The persisted source did not update. In this custom-config path and interrupted shutdown lifecycle,
ProfileLast cannot establish the actual active runtime profile. Do not claim either successful Euro
selection or proven fallback solely from the stale Default readback. No further launch is permitted
by this authorization and none was attempted. Post-error recovery was strictly offline.

No Expert load/init or tester log records were captured. This does not replace positive selection
proof. Default remained byte-identical. Euro contents changed through native terminal behavior;
post-shutdown scan still found4 charts and no Expert/script/custom-code reference. No deliberate
profile edits occurred and no unrelated Expert binary was inspected or modified.

No ResearchWorkspaceIdentity issued; no campaign adapter changes, configuration preview or dry-run.
Prerequisites BLOCKED; NOT_AUTHORIZED; START disabled; executions0; budget0/11; OOS sealed.
Gold Scalper remains1. Frozen1044/historical1621, all research rows, canonical source/artifact and
all tags passed preservation verification. Only this report changed in tracked scope; new ignored
helpers/evidence are under .local/phase5_c2e. No production/test changes, so no fresh full gate.
No commit/tag/push. START authorization is not ready for review as executable.

## Runtime workspace amendment — current result

Current Phase 5C.2E status: BLOCKED_RUNTIME_ATTESTATION_UNAVAILABLE (native timeout).
This supersedes the earlier selection-method blockers, without rewriting earlier evidence.

Read-only project script: src/trading_ecosystem/tester/ResearchWorkspaceAttestor.mq5.
Source SHA-256: b4dbb21090c42cd598ecc6671c57b6893495666cbddceb4efb24a70b25ed636a.
Compiled EX5 SHA-256: f7f53be4c94986e694b11e58853a6aefdf37ac5e3ed41c2a8754e685d710080a.
Pinned MetaEditor6230, 0 errors/0 warnings. Compiler executable SHA:
cf2750bde55d98a1f3b4e56bcdd4f59300d0cff5caa6760985f7ef2c2cc12229.
The campaign reference source and canonical candidate EX5 were not changed or rebuilt.

The script enumerates charts using ChartFirst/ChartNext, reads ChartSymbol/ChartPeriod and
CHART_EXPERT_NAME/CHART_SCRIPT_NAME, and writes diagnostic JSON to the MQL5 file sandbox.
It does not trade, mutate charts, change profiles, write globals, use DLLs or make web requests.
Official read-only property semantics: https://www.mql5.com/en/docs/chart_operations/chartgetstring
and https://www.mql5.com/en/book/applications/charts/charts_string_properties.

A strict Python interpreter validates payload types, exactly one expected attestor host, absence
of any Expert or unexpected script, canonical ordering and unique Euro symbol matching. Volatile
IDs/ordinals/timestamps and supplemental ProfileLast do not affect the fingerprint. Native period
values are preserved in runtime identity; undocumented static period encoding is not inferred.
These interpretation tests do not constitute proof that native collection completed.

Current reviewed static Euro input: four EURUSD charts, no executable attachment references.
Other profiles have different symbol multisets, so the safe Euro fingerprint is distinguishable.
Static symbol fingerprint: 8e72ea16a3636ee44dc0050698b264035ee70c1e421174c2574fe4dc8ae10c86.
Complete file inventories remain in ignored preregistration evidence.

New RUNTIME_WORKSPACE_ATTESTATION launch: c3a2acca-fdeb-40ed-8618-42acf7eebed5.
Exactly one launch under this amendment; total isolation/attestation launches across authorizations3.
Requested /profile:Euro, MAIN_MODE, StartUp Script=ResearchWorkspaceAttestor, ShutdownTerminal=1.
No StartUp Symbol, no Tester section, no /portable terminal switch, no password.
Only the new diagnostic EX5 was exclusively staged under MQL5/Scripts and removed after cleanup.
No repeated external close request was used. Emergency owned-process timeout was60 seconds.

The journal records: script ResearchWorkspaceAttestor (EURUSD,Daily) loaded successfully.
It does not record attestor completion. No output JSON file was found. The launch reached the
60-second ownership timeout, so graceful script-driven shutdown is NOT VERIFIED. The owned job
closed all observed descendants; no terminal/tester process remained. A terminal exit code in
cleanup observations must not be misrepresented as normal script-driven completion.

During this same launch the existing SDK verified pinned terminal/build/data root, DEMO,
Exness Technologies Ltd, Exness-MT5Trial14 and expected salted account fingerprint. This safe
account match was durably written immediately, before shutdown. No raw account ID was persisted.
No tester process or unrelated Expert startup was observed. Absence of such logs is insufficient
for runtime chart isolation. Runtime chart inventory/fingerprint and unique runtime profile match
remain UNAVAILABLE. ProfileLast was not used as the primary test or recaptured for qualification.

Post-launch Default AND Euro file inventories are byte-identical to this launch's pre-state.
Evidence manifest: 44b8eeb6bf1af4be209376a0bd81083567d53f5480de3606af50ab337fe1020d.
Independent readback verified manifest/files and profile integrity. Original two validations remain
unchanged. Runtime root: .local/phase5_c2e/runtime-workspace-attestation.

No ResearchWorkspaceIdentity issued. No campaign adapter binding, configuration preview or
campaign dry-run performed because isolation did not succeed. Prerequisites BLOCKED; campaign
NOT_AUTHORIZED; START disabled; campaign executions0; budget0/11; OOS sealed; Gold Scalper1.
Final START authorization is not ready. No retry, Phase5C.3, commit/tag/push occurred.

Current tracked-scope files (6):
- PHASE5_C2E_REPORT.md
- src/trading_ecosystem/tester/ResearchWorkspaceAttestor.mq5
- src/trading_ecosystem/tester/workspace_attestation.py
- tests/test_workspace_attestation.py
- scripts/verify_phase5_c2e.py
- scripts/verify_phase5_c2e.ps1

The new gate preserves the frozen Phase5C.2D source/probe inventory and prior research rows;
existing verification scripts were not modified. An automatic approval review initially rejected
creation of the new gate by misidentifying it as a frozen-gate overwrite. After verifying the old
gates had no diff and new paths did not exist, exclusive creation of the new files was approved.
No approval bypass or frozen-gate mutation occurred.

Scope deviation: none in this amendment. Timeout is a failed qualification outcome, not permission
to retry. The earlier shutdown helper defect remains separately documented above.

## Final verification completion — 2026-10-16

All applicable full-gate checks PASS, with failures and repairs retained in separate logs.
The original full-gate.log stopped on three public evidence SHA-256 secret-scan findings.
full-gate-resumed.log passed all 1,579 backend tests (including 314 integration tests and
migration tests) in 684.76 seconds, then stopped on formatting of the new verifier only.
The three independently verified public manifest digests have explicit inline allowlist
annotations; the frozen secret scanner and all frozen gates remain unchanged. Ruff formatted
only the new verifier. No production logic or attestor source/binary was changed in this resume.
full-gate-completion.log records the remaining checks after this formatting-only repair:
Ruff PASS; format PASS (412 files); strict mypy PASS (339 source files); secret scan PASS
(526 files); frozen registry PASS; frontend typecheck/lint/format PASS; frontend 178 tests PASS;
production build PASS; scope/ignore/lineage and preservation PASS; git diff --check PASS.
The backend was not unnecessarily rerun after the formatting-only repair.

Final preservation: 1,044 frozen files and 1,621 historical files byte-identical; previous
qualification/probe evidence and all research rows unchanged; all three Phase 5B run manifests
independently verified. No prior gate, UI, reference source, canonical EX5 or tag was modified.
The existing local PostgreSQL cluster was stopped at resume and was started without initialization
or reset to perform the authorized gate. Readback confirmed research data remained unchanged.

Focused workspace tests: 11 passing cases cover canonicalization, volatile fields/order exclusion,
Smart Hedge and other Expert detection, foreign scripts, self-attestor host restrictions, unique
clean Euro match, ambiguous match, inventory changes/mismatch, supplemental-only ProfileLast,
and missing self identity. Actual script-driven shutdown failed qualification; it is not claimed
as tested native success. Adapter/exact WorkspaceIdentity/dry-run implementation and their tests
remain deferred by the explicit prerequisite stop. Campaign/OOS invariants were checked by the
gate against unchanged persisted records. Static timeframe encoding was not interpreted, so a
future successful qualification must also resolve any required static/runtime period comparison.

Final phase status remains BLOCKED_RUNTIME_ATTESTATION_UNAVAILABLE, despite regression PASS.
No runtime chart inventory, runtime fingerprint, WorkspaceIdentity, adapter binding, first-development
configuration identity or successful dry-run exists. Smart Hedge/foreign program absence and unique
Euro runtime matching remain UNVERIFIED. ProfileLast is supplemental and was not used to qualify.
No new native launch occurred during this resume. The amendment's single launch is consumed.
Campaign NOT_AUTHORIZED; START disabled; campaign executions0; budget0/11; OOS sealed;
Gold Scalper executions1. START authorization review is not ready. No commit/tag/push.
