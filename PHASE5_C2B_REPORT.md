# Phase 5C.2B — reference pre-registration and execution authorization contract

Status: IMPLEMENTATION / PRE-REGISTRATION COMPLETE; FULL GATE PASS. NOT READY TO START.

No campaign was started or authorized. The existing portable execution pathway still returns
INITIALIZATION_FAILED. Authorization eligibility and Start fail closed; no native probe was
run to repair this prerequisite. This is a remaining environment qualification blocker, not
a source/build blocker and not a failure inferred from strategy performance.

## Identities

- Reference project: `782bd6a2-4f97-5ca4-906a-cbc1dfe5ce2b`
- Candidate: `b847df2f-2f5b-4941-881a-efaab99300eb` — PROJECT_OWNED_REFERENCE.
- Baseline configuration: `338ffcb4-84ef-504f-9b8c-da7e66103d7c`.
- Frozen definition: `e1dc4c89a6f42dc9e442d5aa4e0411dc1f83fe95219cb16769fe81de92e3f44c`.
- Campaign ID: `acc5933d-3135-524e-a6af-17ae7f77eb1e`.
- Campaign plan identity: `e6dc47596ca2de7b808d4ccdb7e196cfcd4bd8ae229154362dfa7e1e9a99e7b9`.
- Parameter space identity: `03c083af3ccb6d7f94e2fe469ae2a299917aa710699d3079ecef85144abdc510`.
- Budget identity: `e9f84cfefe1efd3cead128988cd61b56d1e6e4d59c1a4b91ec9162902824a513`.
- Split plan identity: `62b6cf6167836aec5b37507689a7bd312754ca0fc6bfb5f3e38e820fde97fcba`.
- Authorization review identity: `5e00c757851b1a21cabdab570115e1f39a5421d9c31270677468539b1da14e89`.
- Authorization state: NOT_AUTHORIZED; no grant identity exists.

## Build contract

Source SHA-256: `4800f441238fd5a0eaff63e7839865770e4af8fcec4f293b6cc40f07a2dcc46f`.
Canonical EX5 SHA-256: `36e7a042cb8c67eb25ade8a9ce1ce37f0314844842c4ae87e0d84003bb0921a1`.
Build provenance identity: `28f063544a252a7f2ae09408cb6c0875e6e89223ffd91147917d6f164427ede7`.
Compiler SHA-256: `cf2750bde55d98a1f3b4e56bcdd4f59300d0cff5caa6760985f7ef2c2cc12229`; MetaEditor 6230.
Canonical compile diagnostics SHA-256: `cd27bd912b6504a014dabc5067aab90213148e82b10ceaa7c4bbcfdf334e5a82`.

SOURCE_REPRODUCIBLE=VERIFIED; BUILD_REPEATABILITY=VERIFIED;
BIT_REPRODUCIBLE=NOT_ESTABLISHED; CANONICAL_ARTIFACT=PINNED.
COMPILER_OUTPUT_NONDETERMINISM_CAUSE_UNKNOWN. No EX5 binary-format investigation was needed.
The first successful qualification build was selected explicitly, before any performance observations.
All four qualification compilations completed with 0 errors / 0 warnings. Build hashes:

1. `36e7a042cb8c67eb25ade8a9ce1ce37f0314844842c4ae87e0d84003bb0921a1`
2. `2706401b8a69901205c42d36a8b402c7701d6ab21f9467d70ecef366e89eaf45`
3. `70dc1bf901c9cfa58cd159ef8c63a52684cdcc7a6f8745bbf337a1b3ca107eab`
4. `4984a7ec707af79d48fc7ddcc9347d17d83ea330f6b1bf2ba74ca3028536bfa6`

The build decision permits different rebuild bytes. A rebuild is a new artifact and cannot
silently replace the registered artifact. Source and canonical EX5 are both bound into the
definition and campaign authorization. Source bytes are revalidated against the pinned hash;
a checkout with different line endings fails identity verification until exact source is restored.
Compiler output and receipts remain Git-ignored under `.local/phase5_c2b`.

## Frozen research specification

Project source exposes InpFastEmaPeriod=20 and InpSlowEmaPeriod=100. Closed-bar EMA crossover
uses bars 1 and 2 only; fixed lot 0.01; magic 52020001; at most one owned symbol position;
opposite signals close before entry. M5 DEMO tester only, optimization disabled; no third-party
includes, DLL, WebRequest, file IO, randomness, pyramiding, martingale or trading grid.
Compiled syntax is verified; native strategy behavior has not been executed in this phase.

Parameter provenance: PROJECT_SOURCE, represented by the existing STRATEGY_SPECIFICATION
parameter enum plus exact source hash. Choice rationale: OPERATOR_DEFINED_RESEARCH_HYPOTHESIS.
Fast choices 10/20/30; slow choices 60/100/140; all nine pairs satisfy Fast < Slow.

Objective: MAXIMIZE NET_PROFIT for exploratory pipeline qualification only.
Constraint: TRADE_COUNT >= 10. Zero trades remains a valid observation but is ineligible.
DEVELOPMENT ranking: NET_PROFIT descending, configuration identity ascending; top two eligible.
Selection is frozen before VALIDATION. EXPLORATORY_GROSS remains unchanged.
Budgets: DEVELOPMENT 9, VALIDATION 2, total native maximum 11; reservations consumed 0.
Wall-time cap 6,600 seconds (11 × existing 600-second timeout); one worker; no spare executions.

| Stage | Start inclusive | End exclusive | Identity |
| --- | --- | --- | --- |
| DEVELOPMENT | 2026-01-01 | 2026-04-01 | `96dc3c835fefdc64d3cb38b51fee4d0a22d67d087716ee697641673dc67b1569` |
| VALIDATION | 2026-04-01 | 2026-05-16 | `cca8579a75de56e6d7482e0296069ddebb93c185febb606bf21baeaed276ec69` |
| LOCKED_OOS | 2026-05-16 | 2026-07-01 | `3732473557256b4bc2a2b864778fc751aa665a6f7eac999c63bd9e764a5f1fa5` |

These half-open boundaries preserve the authorized inclusive calendar dates. LOCKED_OOS is
sealed and denied. The prior raw report is an evidence reference for observed history, not
a guarantee of future tick availability. No OOS performance or future metrics were exposed.

## Ordered deterministic preview

| Ordinal | Configuration identity | Fast | Slow |
| --- | --- | --- | --- |
| 0 | `dc26086172e14a1eaf778dcb466cb62dc77a30d4b1aa0638173ff0b5ad98078a` | 10 | 60 |
| 1 | `2de742c2f6e40308f424e981c17e5917e8f8db8392240445ab0fcfd9408cd09b` | 20 | 60 |
| 2 | `1cda76de10394f9f3daa9e9ef07c2def44feb7d6d6a1a5e7ac66270b0dc81076` | 30 | 60 |
| 3 | `f6bccd2b2b489de20056520b61faa5e812936063c3d486d62e07598b55d16b29` | 10 | 100 |
| 4 | `de03ddc3e057e2655a17000cdfe15e3f3f6c9ef996b42551496887198be204e7` | 20 | 100 |
| 5 | `c14bb10e583b096de9d7e920a821278a070a4189ccdcb755e9be95aa997b340e` | 30 | 100 |
| 6 | `a7a04f4be0eb8b1c24b136efc87056b513f3195a093a806bb6f45e2f0fef44ff` | 10 | 140 |
| 7 | `f258268ec4385d30791f2396279363a69b4a5cd2552c79c2c7f00fa4f8f759a3` | 20 | 140 |
| 8 | `f7bbb589161d65fa4a8c5e8ca1ab18eceb0600dac2399c9733af6fe01e199227` | 30 | 140 |

## Authorization and compatibility

The reference protocol is an explicit extension. The original V1 schema still rejects a
profit-only objective and retains its original all-ties/Pareto selection behavior. Existing
contract tests remain unchanged. Shared parser entry points dispatch on reference_protocol.
The reference extension requires the exact source-backed domains, activity constraint, splits
and 9+2 budget; unsupported combinations fail closed.

Capability binds campaign ID/plan, candidate, canonical artifact/source/build, definition,
parameters, budget, splits, objective, constraints, baseline and research environment.
Allowed stages are DEVELOPMENT/VALIDATION; LOCKED_OOS is explicitly denied.
The operator confirms the exact review identity. Grant storage and Start are separate operations.
The API gates worker creation, the native runner gates reservations, and the native boundary
revalidates source/artifact/authorization before handoff to the existing Phase 5B Service.
No second execution infrastructure was introduced. The portable environment blocker was retained.

Workbench shows the nine ordered candidates, frozen dossier, 9/2/11 budget, provenance,
objective, constraint and authorization review. Authorize and Start are disabled because the
backend reports INITIALIZATION_FAILED. Desktop and 390px browser inspection passed; no Start
or Authorize action was invoked. Screenshots are ignored runtime evidence.

## Verification

- Backend: 1536 PASS, including 314 PostgreSQL/integration tests.
- Frontend: 177 PASS (5 new authorization tests); backend additions: 19 tests.
- Ruff, Python format, strict mypy, secret scan: PASS.
- Frontend typecheck/lint/format/production build: PASS.
- Fresh isolated database migrations/idempotency: PASS; no production schema migration needed.
- Scope, Git-ignore, tags/lineage, registry, git diff --check: PASS.
- Frozen evidence: 1,044 byte-identical; historical evidence: 1,621 byte-identical.
- Every existing row in the eight Phase 5B tables remains exactly unchanged.
- Exactly one new project/candidate/artifact/attestation/baseline configuration and frozen
  reference definition/campaign were added by explicit authorization; no old record changed.
- BaselineRuns remain 3; BaselineResults 0; derived publication 1; Gold Scalper executions 1.
- Reference native executions 0; campaign runs 0; consumed native reservations 0.

Full gate command: `scripts/verify_phase5_c2b.ps1`; final log:
`.local/phase5_c2b/full-gate-final.log`. First gate stopped at two non-secret hash literals;
targeted identity annotations corrected the findings; scanner rules were not weakened.
An intermediate gate also rejected a new .gitattributes rule as a frozen-file change.
That rule was removed; frozen scope tests were preserved and the full gate rerun.

## Files changed (24)

- `PHASE5_C2B_REPORT.md`
- `dashboard/src/workbench/CampaignAuthorization.tsx`
- `dashboard/src/workbench/CampaignPanel.tsx`
- `dashboard/tests/campaign-authorization.test.tsx`
- `scripts/prepare_phase5_c2b.py`
- `scripts/verify_phase5_c2b.ps1`
- `scripts/verify_phase5_c2b.py`
- `src/trading_ecosystem/experiments/ReferenceEmaCrossM5.mq5`
- `src/trading_ecosystem/experiments/api.py`
- `src/trading_ecosystem/experiments/authorization.py`
- `src/trading_ecosystem/experiments/baseline_boundary.py`
- `src/trading_ecosystem/experiments/campaign_api.py`
- `src/trading_ecosystem/experiments/campaign_runner.py`
- `src/trading_ecosystem/experiments/campaign_store.py`
- `src/trading_ecosystem/experiments/campaigns.py`
- `src/trading_ecosystem/experiments/reference_contract.py`
- `src/trading_ecosystem/experiments/reference_preparation.py`
- `src/trading_ecosystem/experiments/store.py`
- `src/trading_ecosystem/tester/qualification.py`
- `src/trading_ecosystem/tester/readiness.py`
- `src/trading_ecosystem/workbench/contracts.py`
- `src/trading_ecosystem/workbench/store.py`
- `tests/integration/test_reference_campaign.py`
- `tests/test_reference_campaign.py`

## Remaining blocker / deviations

A separate first-real-campaign START authorization cannot safely be issued yet. The existing
portable environment has not been qualified for native execution; no environment repair or
probe was performed. Pre-registration and the authorization contract are complete, but the
campaign is NOT_AUTHORIZED and remains technically ineligible to start.

Gold Scalper remains BLOCKED_PARAMETER_PROVENANCE, without guessed inputs or another execution.
The user-approved build contract replaced the initial bit-identical-build interpretation.
No campaign execution, OOS access, Phase 5C.3, commit, tag or push. No other deviations.
