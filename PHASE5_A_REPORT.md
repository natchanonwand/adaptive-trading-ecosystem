# Phase 5A — Research Workbench MVP

Status: **IMPLEMENTATION COMPLETE / PASS**. The complete Phase 5A gate exited 0.

Baseline: `2b4a736` (Phase 4E). No commit, tag or push performed.

## Implemented surface

Local UI: `http://127.0.0.1:8785/workbench`.

- `#/projects`: empty/populated project cards, status, asset, product, updated time, pagination.
- `#/projects/new`: six-step External EA wizard, catalog/custom candidate, opaque EX5,
  optional PDF, explicit DEMO binding, UNKNOWN metadata, review and idempotent creation.
- `#/projects/{id}`: Overview and Evidence, baseline readiness, nonexecuting Run Baseline
  notice, and explicit Experiments/Behavior/Forward placeholders.

Catalog: Gold Scalper for MT5 EA / XAUUSD / transparent/simple pilot;
BTC AutoTrader / BTCUSD / breakout/pending pilot;
Artemis NAS100 ORB Edge / US100 / ORB/index pilot. No vendor links or binaries invented.
Selection conveys no endorsement or profitability claim.

## Persistence and storage

Existing SQLAlchemy/PostgreSQL conventions, additive `workbench` schema and separate
Alembic `0001_projects` lineage. Public journal and monitoring schema are unchanged.
Artifacts, candidates and projects persist as validated immutable contracts; project
and candidate creation is atomic. Repeated migration application is tested.

EX5/PDF bytes stay opaque in Git-ignored `.local/artifacts/research_projects/`.
SHA-256 + role deduplicates to the first artifact identity/name/time. Size limit is
16 MiB. Files are verified on registration, project creation and detail readback;
tampering forces NOT_READY. Existing bytes are never overwritten. No binary is tracked.
Candidate registration is atomic within project creation, rather than a separate
orphan-candidate endpoint. API details and operator setup are in
`docs/PHASE5_A_RESEARCH_WORKBENCH.md`.

The tested migration was applied to the existing local DEMO application database.
The Workbench service is metadata-only, bound to loopback port 8785. Browser review
used empty state and wizard/catalog; no demonstration project was inserted into the
application database. Synthetic onboarding fixtures run in fresh test databases.

## Verification

The successful final gate log is `test-results/phase5_a-full-gate-v2.log`;
the earlier attempt is retained as `test-results/phase5_a-full-gate.log`.
JUnit is `test-results/phase5_a.xml` (Git ignored).

| Check | Result |
|---|---|
| Full backend regression | PASS — 1,114 tests |
| PostgreSQL/integration (included above) | PASS — 199 tests; 40 new Workbench tests |
| Ruff / Ruff format | PASS — 291 formatted files |
| Strict mypy | PASS — 247 source files |
| Secret scan after fixture annotation | PASS — 369 project files |
| Frontend regression | PASS — 82 tests across 9 files; 7 new Workbench tests |
| Frontend typecheck / lint / format | PASS |
| Production build | PASS — monitoring and Workbench entries |
| Migration checks | PASS — repeated upgrade, unchanged public journal head |
| Frozen source preservation | PASS — 347 prior files unchanged; Vite build entry only |
| Frozen evidence preservation | PASS — all 1,044 files byte-for-byte unchanged |
| Frozen benchmark registry | PASS |
| Scope / binary Git-ignore / whitespace | PASS |
| Complete `verify_phase5_a.ps1` | PASS — exit 0 |

Visual review: desktop 1280 × 900 and mobile 390 × 844 viewport settings; measured
content widths 1265 and 375 respectively, with equal scroll/client widths (no horizontal
overflow). Captures: `test-results/phase5_a-desktop.png` and
`test-results/phase5_a-mobile.png`. Built UI renders using the existing design styles.

Initial targeted integration attempt failed because local PostgreSQL was stopped.
The existing isolated instance was started and the targeted suite passed. Synthetic
credential-rejection strings triggered secret scanning; only those explicitly synthetic
fixture lines were annotated. The scanner and all prior tests remain unchanged.
The formatter initially moved one annotation away from its fixture; this was corrected
on the exact line and the complete gate rerun. No production credential was involved.

## Files created or changed

Modified existing file:

- `dashboard/vite.config.ts` — adds only a second production build entry.

Created files:

- `alembic-workbench.ini`
- `migrations/workbench/__init__.py`
- `migrations/workbench/env.py`
- `migrations/workbench/versions/__init__.py`
- `migrations/workbench/versions/0001_projects.py`
- `src/trading_ecosystem/workbench/__init__.py`
- `src/trading_ecosystem/workbench/__main__.py`
- `src/trading_ecosystem/workbench/contracts.py`
- `src/trading_ecosystem/workbench/store.py`
- `src/trading_ecosystem/workbench/api.py`
- `dashboard/workbench.html`
- `dashboard/src/workbench/main.tsx`
- `dashboard/src/workbench/api.ts`
- `dashboard/src/workbench/Workbench.tsx`
- `dashboard/src/workbench/workbench.css`
- `tests/integration/test_workbench.py`
- `dashboard/tests/workbench.test.tsx`
- `scripts/verify_phase5_a.ps1`
- `scripts/verify_phase5_a_scope.py`
- `docs/PHASE5_A_RESEARCH_WORKBENCH.md`
- `PHASE5_A_REPORT.md`

Generated local artifacts: preservation snapshot `.local/phase5_a/baseline.json`,
test logs/JUnit/screenshots in `test-results/`, and production assets in `dashboard/dist/`.
All are Git ignored. No dependency lockfile or old phase implementation changed.

## Limits and scope choices

- Single-user local service; no remote deployment or multi-user authentication.
- License/tester readiness uses explicit user attestations, not vendor verification.
- Project metadata is immutable after creation; corrections require a new project.
- Cancelled/unassociated uploads are retained; automatic cleanup is not implemented.
- Manuals are PDF-only; optional known magic is limited to nonnegative JS-safe integers.
- No arbitrary-secret detector can recognize every unlabeled value; credential fields
  are forbidden and credential-shaped assignments are rejected.
- Full backend/frontend regression and byte preservation replace rerunning collectors
  that could rewrite frozen evidence. No historical research rerun is performed.
- No execution, optimization, downloads, broker writes or Phase 5B work was added.
