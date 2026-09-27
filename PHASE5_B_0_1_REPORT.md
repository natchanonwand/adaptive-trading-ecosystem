# Phase 5B.0.1 — Baseline readiness semantics

Status: COMPLETE / PASS. Scope: readiness/state derivation only.
Starting tree was clean at `3a35373a7d022fe61a7289a18c33243a8f8fb178`, tagged
`phase5b-tooling-v0.1.0`; HEAD and origin/main agree. No tag, commit or push is
part of this correction.

## Root cause

Both Workbench `readiness()` and tester preflight used a negative comparison
against affirmative declarations. Consequently UNKNOWN was treated as a license
or tester prohibition. In addition, list/detail responses replayed the creation-time
project status, so fixing new-project creation alone would leave existing badges wrong.

## Corrected derivation

- UNKNOWN means not yet verified. With a verified artifact and valid explicit
  DEMO broker/symbol/timeframe binding, readiness is BASELINE_READY.
- Explicit NOT_AUTHORIZED yields BLOCKED_LICENSE. Explicit UNAVAILABLE tester
  access yields BLOCKED_TESTER_ACCESS. Native license/tester denial retains those
  typed failure states and separately records LICENSE_BLOCKED or TESTER_ACCESS_BLOCKED.
- Declarations remain unchanged after observations. No license enforcement,
  confirmation requirement, artifact validation or tester safety configuration is bypassed.
- Current list/detail readiness is calculated from declarations, binding and actual
  artifact verification. Previously stored creation status/history is retained,
  not rewritten; no data migration is required. Existing legacy BLOCKED_TESTER
  values remain readable, but new explicit prohibitions use BLOCKED_TESTER_ACCESS.
- Missing/changed artifacts remain NOT_READY; missing bindings remain blocked
  for their actual reason. UNKNOWN alone never supplies a blocked reason.

## Gold Scalper PRO Acceptance

Project ID: `1b55ae30-d498-4e75-aa4e-74fb97bf62e9`.
Before correction, the running HTTP service reported BLOCKED_LICENSE with
VERIFIED artifact, UNKNOWN license, UNKNOWN tester access, DEMO, XAUUSDm, M5.
Post-restart HTTP verification passed on both the project list and detail API:

| Field | Current value |
|---|---|
| Project status (list and detail) | BASELINE_READY |
| Baseline readiness | READY |
| Artifact verification | VERIFIED |
| Declared license | UNKNOWN |
| Declared tester access | UNKNOWN |
| Environment / symbol / timeframe | DEMO / XAUUSDm / M5 |
| Baseline runs / results | 0 / 0 |

The stored creation-time status/history is historical and unchanged; the current
readiness projection is authoritative for badges and baseline eligibility.

The before-state database snapshot contains one project, one candidate, one
artifact, zero baseline runs and zero baseline results. Read-only row hashes are
recorded in `.local/phase5_b_0_1/database-before.json`. Independent after-state
readback in `database-after.json` matched every table hash/count exactly.
`gold-http-after.json` records the corrected API fields. Declarations, history,
artifact metadata and execution records were not modified.

## Tests and gate

Added cases cover UNKNOWN/UNKNOWN and UNKNOWN/confirmed readiness; explicit
license/tester prohibition; legacy stored unknown-blocked status projections;
unchanged stored history and artifact tampering; simulated success, license denial,
tester denial and initialization failure with declarations preserved; and the
Workbench BASELINE READY badge, visible UNKNOWN values and absence of automatic start.
Updated old assertions only where they encoded the incorrect UNKNOWN-is-blocked rule.
Tester callbacks in integration tests are synthetic; no EA or native Strategy Tester runs.

Focused PostgreSQL tests: 70 passed. Focused Baseline UI tests: 15 passed.
Complete Phase 5B gate: PASS, exit 0 (`test-results/phase5_b_0_1-gate.log`).

| Verification | Result |
|---|---|
| Backend regression | 1,216 passed |
| PostgreSQL/integration subset | 229 passed, included above |
| Frontend regression | 97 passed |
| Ruff / Python format / strict mypy / secret scan | PASS |
| Frontend typecheck / lint / format / production build | PASS |
| Phase 5A regression / Phase 5B scope / Git diff check | PASS |
| Previously frozen evidence | 1,044 files unchanged |
| Database before/after row hashes | Identical; zero baseline runs/results |

This correction adds 10 backend cases and one UI case, and adjusts the old
UNKNOWN-is-blocked assertions to the authorized semantics. No EA or native
Strategy Tester was run. The only restarted application was the verified idle
local Workbench web service, to load the corrected derivation.

The scope verifier previously required HEAD/origin to remain at Phase 5A, which
cannot hold after the user's completed Phase 5B freeze. It now pins the exact
Phase 5B commit/tag and permits only this correction's files. Both original
Phase 5A tags, ancestry, other snapshot bytes, historical research evidence,
broker-write exclusions, ignored artifacts and tester configuration checks remain enforced.

## Files changed

1. `src/trading_ecosystem/workbench/contracts.py`
2. `src/trading_ecosystem/workbench/store.py`
3. `src/trading_ecosystem/workbench/api.py`
4. `src/trading_ecosystem/tester/contracts.py`
5. `src/trading_ecosystem/tester/service.py`
6. `dashboard/src/workbench/BaselinePanel.tsx`
7. `tests/integration/test_workbench.py`
8. `tests/integration/test_baseline.py`
9. `dashboard/tests/baseline.test.tsx`
10. `scripts/verify_phase5_b_scope.py`
11. `docs/PHASE5_B_AUTOMATED_BASELINE.md`
12. `PHASE5_B_0_1_REPORT.md` (new)

No tuning, Phase 5C, execution, license bypass, commit, tag or push.
