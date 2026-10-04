# Phase 5B.1H — installed-profile execution bridge and gate stabilization

Status: **IMPLEMENTATION COMPLETE / PASS — non-executing qualification only.**

Baseline: `phase5b-tooling-v0.1.10`, commit
`46f2c3d09beabae8a9d44c5ec7d3e1dbe5e899ed`.
No commit, tag, push, infrastructure probe or real candidate execution is authorized here.

## Frontend diagnosis

The unchanged two cases passed separately (1,449 ms and 895 ms), and together
(1,254 ms and 547 ms). The unchanged normal suite reproduced two 5-second timeouts:
the upload case and the six-step catalog wizard. This changing failure set and the
isolated passes did not support an API/mock mismatch or fixed unresolved promise.
Under normal worker concurrency, jsdom initialization consumed 97.77 seconds in
aggregate; the suite had 103 passes and two failures. Changing only concurrency to
one worker produced 105 passes, with the target cases at 1,124 ms and 532 ms and
37.89 seconds of aggregate jsdom initialization.

The demonstrated cause is contention during concurrently initialized jsdom suites
on this workstation, exhausting the existing wall-clock test budget. The correction
sets one worker, retaining per-file isolation, all assertions, and the original
5-second timeout. The upload test additionally waits for the completed Overview
navigation so teardown cannot precede its final asynchronous navigation.
Two normal full-suite validations after correction passed 105/105 (76.76 s and
73.55 s). Production build passed. No retry-until-green or timeout inflation was used.
Diagnostic logs are under ignored `.local/phase5_b1h/`.

## Execution contract

The common Baseline service selects strategy from the current explicit authorization
event and requires that event to match the immutable attempt. USER_SUPPLIED_EX5 uses
the existing portable adapter; Marketplace-installed candidates use the installed
transport without passing EX5 bytes to staging. Unsupported provenance fails closed.

The installed transport consumes the existing persisted qualification from
`phase5_b1g/qualification.json`, checks its digest, independently requalifies its
exact candidate/configuration/artifact/profile/proof identities, and freezes an
immutable execution plan. No candidate filename search or arbitrary-path endpoint
is introduced. The plan contains native config/report targets, identity bindings,
fixed timeout and the single owned-process lifecycle contract. It is written
exclusively into the new attempt namespace and contributes to the final manifest.

Before a future native launch, the adapter revalidates the live DEMO account against
the original salted account fingerprint, validates terminal/profile/server identity,
gracefully closes only that verified session, and rechecks the plan and artifact.
Common.Login is ephemeral and is removed; credentials are never persisted. The
candidate stays installed in place. Only appended logs and the new UUID report are
captured; the raw report hash and sanitized report are retained. Cleanup removes
only that attempt's generated report namespace and temporary config.

The existing service owns state transitions, cancellation, parser, validation,
normalized result, manifest and database persistence for both transports. Installed
reports must name the qualified Expert (relative reference or its exact leaf stem),
and still match symbol, timeframe, dates, deposit, leverage and real-tick evidence.
Typed pre-launch blockers remain distinct from initialization failures.

## Verification and immutability

- Initial clean HEAD/origin/tag prerequisite passed; all 22 tags preserved.
- Initial 1,044 frozen files and 1,495 historical files verified byte-for-byte.
- Nine additional Phase 5B.1G qualification files and the prior acceptance-preflight
  manifest also verified; seven production database tables unchanged.
- New synthetic PostgreSQL tests: 23 passed. Earlier combined bridge/portable/safety
  coverage passed 129 tests; final isolated bridge/Workbench coverage passed 69 tests.
  All native process and account interactions in bridge tests are fakes.
- The new module uses its own disposable database so its projects do not contaminate
  the prior suite's paginated fixtures. Prior test assertions remain unchanged.
- Strict mypy: passed, 291 source files.
- Real persisted qualification produced an independently reloaded non-executing plan:
  `621ddaed0b63bbe6710ab9f92129410e7f67ac6a6bae4158ca86c4e7497824cf`.
  Its UUID is a validation namespace, not a database BaselineRun.

## Final complete gate

`scripts/verify_phase5_b.ps1` completed successfully. Authoritative log:
`test-results/phase5_b1h-final-gate-4.log`, SHA-256
`69cbf57ee69273ecd06eb9c99302801c8c31b590d8f30ade758612eb61b71bb6`.

| Check | Result |
| --- | --- |
| Backend regression | PASS — 1,400 tests, no skips/errors/failures |
| PostgreSQL/integration (included above) | PASS — 279 tests |
| Frontend regression | PASS — 105 tests, 12 files |
| Ruff / Python format | PASS — 348 files formatted |
| Strict mypy | PASS — 291 source files |
| Secret scan | PASS — 436 project files |
| Frontend typecheck / lint / format / production build | PASS |
| Migrations / scope / Git-ignore / frozen lineage | PASS |
| Frozen evidence | PASS — 1,044 files byte-identical |
| Historical evidence | PASS — 1,495 files unchanged |
| Additional qualification evidence / prior acceptance manifest | PASS — 9 files and manifest unchanged |
| Existing finalized BaselineRun manifests | PASS — 2 independently verified |
| Production database preservation | PASS — all seven table snapshots unchanged |
| Prior Git tags | PASS — all 22 unchanged |
| git diff --check | PASS |

Post-gate independent validation is recorded in
`.local/phase5_b1h/final-preservation.json`. The real candidate plan was rederived
from the persisted qualification, compared with its saved readback, and remained
identical. No native SDK or process call was made for this real validation.

## Exact changed file set

1. `dashboard/tests/workbench.test.tsx` — await final navigation, preserve all assertions.
2. `dashboard/vite.config.ts` — one isolated jsdom worker, unchanged timeout.
3. `scripts/verify_phase5_b_scope.py` — current phase allowlist; exact reconstruction
   of the two authorized frontend additions instead of broad byte-check exemptions.
4. `src/trading_ecosystem/tester/checkpoint.py` — pin the immediate v0.1.10 checkpoint.
5. `src/trading_ecosystem/tester/contracts.py` — precise installed/profile/account blockers.
6. `src/trading_ecosystem/tester/service.py` — explicit strategy dispatch and shared lifecycle.
7. `src/trading_ecosystem/tester/execution_plan.py` — immutable plan and identity/account checks.
8. `src/trading_ecosystem/tester/installed_execution.py` — installed transport, no EX5 staging.
9. `tests/integration/test_installed_execution.py` — 23 synthetic tests and isolated database.
10. `PHASE5_B1H_REPORT.md` — this report.

Generated diagnostic logs, plans and preservation snapshots remain Git-ignored.

## Intermediate failures and deviations

- The first full backend run had 1,335 passes and 61 setup errors from one monitoring
  migration subprocess failure. Its driver detail was suppressed by the unchanged
  test. A controlled bridge/monitoring diagnostic passed 84 tests; subsequent complete
  backend runs passed that migration. The original subprocess cause remains unproven;
  no frozen migration or test was changed.
- The next run exposed pagination fixture contamination from the new tests
  (1,399 passes, one failure). The new module now owns a separate disposable database;
  the original Workbench test and pagination behavior were preserved.
- A later run passed all 1,400 backend tests but stopped on Prettier formatting of the
  two edited frontend files. Only their formatting was corrected.
- All failed logs are retained. Final success is the complete fourth gate, followed
  by independent evidence/database/tag validation. No verification was weakened.
- No scope deviations, native attempts, Git mutations or acceptance retries occurred.

## Limits and next acceptance

Gold Scalper native executions: **0**. New real BaselineRuns: **0**. New real
BaselineResults: **0**. The one real acceptance attempt remains unused.
No fresh SDK/account observation was performed in this phase; the real dry-run uses
historical qualification and validates file/database identities only. Native behavior,
license/tester access, report shape and full-interval real ticks remain unobserved.

The Workbench continues to require explicit operator confirmation and does not
auto-enable execution from dry-run readiness. Its existing environment readiness
projection remains historical. This implementation does not claim a fresh native
qualification. A later acceptance requires its full immediate pre-launch checks.
It must **not begin from this dirty, uncommitted implementation tree**. The completed
implementation must first be frozen under separate authorization, then satisfy the
clean-tree and fresh terminal/profile/DEMO-account/authorization/artifact/configuration
hard gates. Successful fake-boundary tests do not prove real candidate behavior.
Persisted qualification loading currently uses the single explicitly configured
qualification namespace; other candidates fail closed until explicitly qualified.

No prior BaselineConfiguration, BaselineRun, result, probe, report or frozen tag was
edited. No optimization, Phase 5C, behavior inference or forward trading was performed.
