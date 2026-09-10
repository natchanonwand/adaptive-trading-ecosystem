# Adaptive Trading & Portfolio Monitoring Ecosystem

Phase 1 implements contracts and safe foundations only. The owner-approved [spec-v0.1.0 baseline](docs/PRODUCT_SPEC.md) remains authoritative. There is no trading strategy, risk-engine behavior, broker integration, market-data ingestion, web application, or live execution. All entry permission decisions are disabled, including when another declared runtime mode is selected.

See [ADR-001](docs/ADR-001-runtime-storage.md) for decisions and [PHASE1_REPORT.md](PHASE1_REPORT.md) for verification and limitations. Phase 2 requires separate owner authorization.

## Development setup (Windows 11 / PowerShell)

Install uv and PostgreSQL 17 locally, then from the repository root:

```powershell
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
uv python install 3.12
uv sync --locked
```

The committed `uv.lock` pins dependency versions and distribution hashes. The `src` package is installed into `.venv`. Use `uv run --locked` to run tools. No credentials belong in this repository; `.env.example` contains variable names only. Existing `.env` files are neither read automatically nor modified. Set environment variables explicitly through an approved local secret facility. Unknown `TE_` settings and any request to enable entries are rejected. Supported variables:

| Name | Meaning |
|---|---|
| TE_RUNTIME_MODE | Optional; defaults to RESEARCH; only the five specified modes exist |
| TE_ENTRY_ENABLED | Optional; only empty, false, or 0 accepted; always disabled |
| TE_DATABASE_URL | Optional secret PostgreSQL+psycopg URL; required for migrations |
| TE_TEST_DATABASE_URL | Local maintenance database used only by disposable integration tests |

## Complete verification

The helper creates an isolated loopback-only PostgreSQL instance under ignored `.local/phase1-postgres`, on port 55439, without changing the installed service. It uses passwordless local trust solely for disposable tests; never use this helper or role for operational data. It requires PostgreSQL 17 binaries at `C:\Program Files\PostgreSQL\17\bin`. Stop it after testing.

```powershell
.\scripts\postgres_sandbox.ps1 -Action Start
$env:TE_TEST_DATABASE_URL = 'postgresql+psycopg://phase1_test@127.0.0.1:55439/postgres'
.\scripts\verify.ps1
.\scripts\postgres_sandbox.ps1 -Action Stop
```

The integration suite creates a uniquely named `phase1_test_<uuid>` database, runs the actual `python -m alembic upgrade head` command, verifies the journal, and drops only that disposable database. Missing test connection configuration fails the suite instead of silently skipping PostgreSQL tests. This fixture's role needs local CREATE DATABASE permission and ownership for deliberate tamper testing. Future operational users must not own the schema or possess trigger-bypass privileges.

For a separately provisioned **empty development database**, set `TE_DATABASE_URL` privately and run:

```powershell
uv run --locked alembic upgrade head
```

The migration creates only `journal_heads`, `journal_events`, and Alembic bookkeeping. Historical event UPDATE/DELETE/TRUNCATE operations are blocked by a database trigger. Destructive downgrade is intentionally unsupported; future corrections are new events.

## Contracts

- Amount types carry Decimal values and currency/asset/quantity-unit labels. Binary floats, NaN and infinities are rejected. Input representation is bounded to 34 digits and exponent magnitude 100. Aware non-UTC timestamps normalize to UTC; naive timestamps fail.
- Use `arithmetic_context()` for precision 34 and ROUND_HALF_EVEN. It restores the caller's context instead of changing process-wide state. Tick and lot functions use exact Decimal/integer ratios to prevent boundary drift and never introduce binary floats. Nearest rounding is explicit, never the default.
- Build immutable `CanonicalPayload` from a mapping, then an `EventDraft`. Hashing uses versioned, tagged canonical JSON; Decimal numeric scale and map insertion order do not change hashes. Lists retain order. Floats and secret wrappers are not accepted as payload values.
- `PostgresJournal` binds to a caller-owned SQLAlchemy connection. `append()` uses a savepoint and account-row lock; the outer transaction controls commit/rollback. Exact event-ID/content retries return the existing envelope; changed content is rejected. Record `recorded_time` once and reuse the complete draft on retry. Replay validates payload, envelope, sequence, chain and account head. There is no historical edit/delete API.
- Parquet support is a protocol only; no data files are fetched or ingested.

## Secrets and hooks

Configuration secrets use `SecretStr`; environment parse errors return generic messages without retained error context. Database engines disable SQL echo and parameter logging. Attach `RedactingFilter` to each application-owned log handler before logging; register configured secret values, and never call `get_secret_value()` outside the database boundary. Exceptions and URL-like log content are suppressed by the filter. No application entry point exists in Phase 1.

```powershell
uv run --locked pre-commit install
uv run --locked python scripts/secret_scan.py
```

Hook configuration uses locked local tools for Ruff, mypy and detect-secrets. The scanner checks tracked and nonignored untracked files, including an accidentally tracked environment file; it prints finding locations/types, never detected values. It does not inspect ignored credentials or local database contents. Git ignore patterns and hooks reduce accidental disclosure but do not replace future CI enforcement and protected branches. Do not bypass them with forced staging of credentials.
