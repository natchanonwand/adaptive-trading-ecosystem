# Phase 5A — Research Workbench MVP

Research Workbench onboards user-authorized opaque artifacts and metadata. It never
executes an EA, accesses MT5, downloads vendor files, verifies vendor licensing, or
produces research results. Baseline READY means metadata and stored-byte integrity
are ready; it does not authorize execution. Phase 5B is unavailable.

## Browser flow

Open `http://127.0.0.1:8785/workbench`. Projects uses `#/projects`, creation uses
`#/projects/new`, and detail uses `#/projects/<project UUID>`. Detail has Overview,
Baseline, Experiments, Behavior, Forward and Evidence panels. The three future
panels are explicit placeholders. Run Baseline displays an unavailable notice only.
Onboarding itself requires no terminal or database knowledge.

The six-step wizard selects External EA, a custom candidate or catalog entry,
optional files, explicit DEMO binding, user metadata and a review. Future source
types are disabled. A project without an EX5 is a DRAFT. Empty optional metadata
becomes UNKNOWN. A manual is optional and PDF-only in this MVP. Files are capped
at 16 MiB each. Magic numbers are optional nonnegative JavaScript-safe integers.
Do not enter credentials into free text; credential-shaped assignments are rejected,
but the application cannot identify every arbitrary secret pasted as unlabeled text.

Catalog seeds are metadata only, with source/vendor/version UNKNOWN:

| Product | Asset | Research class |
|---|---|---|
| Gold Scalper for MT5 EA | XAUUSD | transparent/simple pilot |
| BTC AutoTrader | BTCUSD | breakout/pending pilot |
| Artemis NAS100 ORB Edge | US100 | ORB/index pilot |

Selection implies neither endorsement nor profitability and supplies no license or
binary. Broker symbols are entered and confirmed explicitly: BTCUSDm, XAUUSDm,
USTECm for BTCUSD, XAUUSD, and USTEC100/US100 respectively. LIVE is rejected.

## Persistence and identity

The existing PostgreSQL/SQLAlchemy/Alembic conventions are reused. The additive
`workbench` schema has artifacts, candidates and projects tables, with an independent
`0001_projects` Alembic version, following the existing monitoring schema convention.
The public `0001_journal` head must already exist and is not changed. No old migration
is edited. Downgrade refuses implicit evidence deletion.

Candidate and project metadata are inserted atomically. Client-generated project
UUIDs make identical retries idempotent; changed content under the same UUID fails.
Candidate IDs are assigned once. Status/history are persisted, with transitions
bounded at BASELINE_READY. Future state names exist as contracts, not running workflows.
License and tester access are user attestations, not vendor-verification results.
BLOCKED_ATTRIBUTION is reserved; optional magic/comments do not claim observed attribution.

Opaque bytes live at `.local/artifacts/research_projects/<sha256>.ex5` or `.pdf`,
already Git ignored. Only hashing, size, filename and time are recorded. There is
no parsing, execution or artifact-download endpoint. Same hash and role reuses the
original identity/filename/upload time. Existing mismatched bytes are never overwritten.
Detail rehashes files; missing/tampered evidence makes baseline NOT_READY. Uploads
cancelled before project creation and bytes from failed metadata transactions are
retained locally, not silently deleted. There is no garbage collection in this phase.
Backup must include both PostgreSQL metadata and the local byte store.

Projects in this MVP are immutable after creation: corrections require a new project.
Pagination uses 50 records in stable UUID order. No generic workflow/edit engine was added.

## Local service and API

Operator setup, once: configure the existing `TE_DATABASE_URL`, apply
`python -m alembic -c alembic-workbench.ini upgrade head`, build `dashboard` with
`npm run build`, then start `python -m trading_ecosystem.workbench` from the repo root.
The application uses the existing settings loader and binds only 127.0.0.1:8785.
Uploaded bytes and database credentials are never served. This is a single-user local
workbench; multi-user authentication and remote deployment are out of scope.

| Method | Path | Purpose |
|---|---|---|
| GET | /workbench-api/catalog | Metadata seeds |
| GET | /workbench-api/projects?offset=0 | Project list |
| POST | /workbench-api/artifacts | Register opaque EX5/PDF bytes, base64 JSON |
| POST | /workbench-api/projects | Atomically register candidate and project |
| GET | /workbench-api/projects/{id} | Detail and integrity verification |
| GET | /workbench-api/candidates/{id} | Candidate metadata |

Writes require same-origin/loopback Host and a custom request header. No CORS is
enabled. API errors suppress driver details and user input. Static routes allow
only the built Workbench HTML and JS/CSS assets. The monitoring API remains GET-only.
Vite gains a second production entry; existing monitoring screens remain unchanged.
Use the built local service for Workbench, not the monitoring-only Vite dev proxy.

## Verification

`scripts/verify_phase5_a.ps1` runs the entire backend suite including real PostgreSQL
and repeated migration application, Ruff/format/strict mypy/secrets, frozen benchmark
hash verification, all frontend checks/tests/build, scope/ignore/whitespace checks,
and read-only preservation checks of the 1,044 prior evidence files before and after.
The baseline code anchor is `2b4a736`; only Vite's reviewed second build entry is
allowed to differ among prior files. No frozen evidence collector is rerun or rewritten.
