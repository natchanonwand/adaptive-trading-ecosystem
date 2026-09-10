# Phase 1 report

Status: **COMPLETE — Phase 1 only**. Final complete verification passed on 2026-09-09. Scope: ROADMAP Phase 1 only. Owner approval was supplied after G0; HEAD remains the authoritative `spec-v0.1.0` tag. The eleven baseline specification/review documents are unchanged.

## Decisions and implementation

Implemented a src-layout Python 3.12 project with uv, Pydantic, SQLAlchemy Core, PostgreSQL and Alembic. [ADR-001](docs/ADR-001-runtime-storage.md) records decisions and unresolved D05 items. Immutable contracts normalize aware timestamps to UTC, reject naive timestamps and binary-float monetary input, and bind Decimal arithmetic to precision 34/ROUND_HALF_EVEN. Tick/lot rounding is explicit; no indicators or strategy rules are implemented.

The journal stores canonical immutable event envelopes, payload hashes, full-envelope hashes and per-account sequence/head state. Account locks serialize appends; savepoints and caller-owned transactions provide rollback. Exact retries are idempotent and conflicting event IDs fail. Replay validates hashes, metadata, ordering and head continuity. PostgreSQL triggers block event UPDATE/DELETE/TRUNCATE. Only two Phase 1 tables plus Alembic bookkeeping exist. Parquet is an interface only.

Configuration and entry permission remain disabled for every asset and every declared mode. Secrets use SecretStr and safe environment error boundaries; logging-redaction fixtures cover messages, repr/JSON and exceptions. Git ignores credentials/local state, and detect-secrets checks every tracked/nonignored project file. Locked local pre-commit hooks provide Ruff, mypy and scanning.

## Exact files created or changed

Changed: [.gitignore](.gitignore), preserving the existing patterns and adding Python, uv, secret, environment and local database exclusions.

Created:

- [.env.example](.env.example)
- [.pre-commit-config.yaml](.pre-commit-config.yaml)
- [.python-version](.python-version)
- [PHASE1_REPORT.md](PHASE1_REPORT.md)
- [README.md](README.md)
- [alembic.ini](alembic.ini)
- [docs/ADR-001-runtime-storage.md](docs/ADR-001-runtime-storage.md)
- [migrations/env.py](migrations/env.py)
- [migrations/script.py.mako](migrations/script.py.mako)
- [migrations/versions/0001_journal.py](migrations/versions/0001_journal.py)
- [pyproject.toml](pyproject.toml)
- [scripts/postgres_sandbox.ps1](scripts/postgres_sandbox.ps1)
- [scripts/secret_scan.py](scripts/secret_scan.py)
- [scripts/verify.ps1](scripts/verify.ps1)
- [src/trading_ecosystem/__init__.py](src/trading_ecosystem/__init__.py)
- [src/trading_ecosystem/config/__init__.py](src/trading_ecosystem/config/__init__.py)
- [src/trading_ecosystem/config/redaction.py](src/trading_ecosystem/config/redaction.py)
- [src/trading_ecosystem/config/settings.py](src/trading_ecosystem/config/settings.py)
- [src/trading_ecosystem/domain/__init__.py](src/trading_ecosystem/domain/__init__.py)
- [src/trading_ecosystem/domain/arithmetic.py](src/trading_ecosystem/domain/arithmetic.py)
- [src/trading_ecosystem/domain/canonical.py](src/trading_ecosystem/domain/canonical.py)
- [src/trading_ecosystem/domain/events.py](src/trading_ecosystem/domain/events.py)
- [src/trading_ecosystem/domain/primitives.py](src/trading_ecosystem/domain/primitives.py)
- [src/trading_ecosystem/domain/safety.py](src/trading_ecosystem/domain/safety.py)
- [src/trading_ecosystem/journal/__init__.py](src/trading_ecosystem/journal/__init__.py)
- [src/trading_ecosystem/journal/contracts.py](src/trading_ecosystem/journal/contracts.py)
- [src/trading_ecosystem/persistence/__init__.py](src/trading_ecosystem/persistence/__init__.py)
- [src/trading_ecosystem/persistence/database.py](src/trading_ecosystem/persistence/database.py)
- [src/trading_ecosystem/persistence/journal.py](src/trading_ecosystem/persistence/journal.py)
- [src/trading_ecosystem/persistence/research.py](src/trading_ecosystem/persistence/research.py)
- [src/trading_ecosystem/persistence/schema.py](src/trading_ecosystem/persistence/schema.py)
- [tests/__init__.py](tests/__init__.py)
- [tests/conftest.py](tests/conftest.py)
- [tests/integration/__init__.py](tests/integration/__init__.py)
- [tests/integration/conftest.py](tests/integration/conftest.py)
- [tests/integration/test_postgres_journal.py](tests/integration/test_postgres_journal.py)
- [tests/property/__init__.py](tests/property/__init__.py)
- [tests/property/test_foundations.py](tests/property/test_foundations.py)
- [tests/unit/__init__.py](tests/unit/__init__.py)
- [tests/unit/test_config_security.py](tests/unit/test_config_security.py)
- [tests/unit/test_events.py](tests/unit/test_events.py)
- [tests/unit/test_primitives.py](tests/unit/test_primitives.py)
- [tests/unit/test_scope.py](tests/unit/test_scope.py)
- [uv.lock](uv.lock)

Local artifacts excluded from Git: `.venv`, uv/tool caches, `.local/phase1-postgres`, test caches and `test-results/phase1.xml`. The pre-commit hook is installed locally in `.git/hooks/pre-commit` and its versioned configuration is listed above. No credentials were read from or written to the existing `.env`. No commit or new tag was created.

## Verification results

Final full-suite status: **PASS**, using `scripts/verify.ps1` against isolated PostgreSQL 17.11.

| Check | Final result |
|---|---|
| pytest | 56 passed, 0 failed, 0 skipped; final run 4.03 seconds, no pytest warnings |
| Ruff lint | Passed |
| Ruff formatting | Passed; tool reported `46 files already formatted` |
| strict mypy | Passed; no issues in 32 configured source/test/migration/script files |
| detect-secrets | Passed; 56 tracked/nonignored project files scanned, no findings |
| uv locked sync | Passed; 43 locked packages checked |
| fresh Alembic upgrade | Passed via CLI on a newly created PostgreSQL database; revision 0001_journal |
| journal append/commit/reload | Passed |
| chain / tamper / rollback / concurrency | Passed, including real PostgreSQL fixtures |
| UTC / Decimal / immutable configuration | Passed |
| disabled entry / absent LIVE / absent broker paths | Passed |
| pre-commit | Installed locally; all four hooks passed |
| Git whitespace | Passed; Git emitted only its informational LF-to-CRLF conversion warning |

JUnit evidence is written to ignored `test-results/phase1.xml`; fixtures remove their own disposable databases. The isolated test server is stopped after verification.

The suite includes 56 pytest cases (42 unit, 3 pure property, 11 PostgreSQL integration cases). Hypothesis exercises Decimal bounds, canonical map/hash stability, sequence/hash properties and committed/rolled-back journal transactions. PostgreSQL fixtures create uniquely named disposable databases and run the actual `python -m alembic upgrade head` CLI before create/append/commit/reload checks. Concurrent writers and duplicate retries use separate connections. Deliberate privileged corruption is detected and rolled back.

Initial development findings were fixed: SQLAlchemy URL parse exceptions needed the safe configuration boundary, mypy required explicit test mutation annotations and finite Decimal exponent typing, and Ruff formatting needed cleanup. Windows sandbox restrictions required authorized uv cache access and PostgreSQL startup. A non-fatal pytest cache-permission warning was removed from the reproduction command by disabling pytest's optional cache provider. No runtime test is skipped when PostgreSQL is missing; the suite fails instead.

Verified dependency environment: Python 3.12.14, uv 0.12.11, PostgreSQL 17.11, Pydantic 2.13.5, SQLAlchemy 2.0.52, Alembic 1.19.2, psycopg 3.3.5, Ruff 0.16.6 and mypy 1.20.2. Exact transitive versions and distribution hashes are in [uv.lock](uv.lock). Windows 11 is the owner-specified development baseline.

## Scope and safety evidence

- `test_assets_and_modes` asserts exactly BTCUSD/XAUUSD/USTEC100 and exactly RESEARCH/BACKTEST/PAPER_FORWARD/DEMO_QUALIFICATION/DEMO_OPERATIONAL. Constructing LIVE fails; there is no LIVE enum member or live-enabling configuration.
- `test_all_modes_and_assets_are_entry_disabled` checks all 15 mode/asset pairs. Environment attempts to enable entries or introduce a live setting fail. Runtime mode labels do not implement those services.
- `test_no_execution_package_or_broker_write_implementation` parses every source module, checks imports/function declarations for broker-write paths and verifies the dependency lock excludes broker packages and FastAPI. Manual source review confirms only domain/configuration/journal/database operations and an unimplemented Parquet protocol. No MT5 package, order_send, broker connection or broker-writing implementation exists.
- Fresh migration, committed reload, hash-chain verification, metadata/payload tamper rejection, append-only trigger enforcement, sequence concurrency and complete rollback all have PostgreSQL fixtures. The migration introduces no trading tables.
- UTC normalization, float rejection, precision 34, half-even ties, tick/lot rounding, immutable configuration/payloads, secret redaction, deterministic hashing and replay have passing fixtures in the final suite.

## Remaining issues and limits

No later phase is authorized. D01–D04 and D06–D08 remain blocked as recorded in the approved specifications; D05 is resolved only for the development stack. Deployment identity/secrets, restricted database roles, TLS, retention, backup/restore targets, external audit anchors, production workload targets and CI enforcement remain unresolved. These do not authorize operational execution.

The local test cluster uses loopback trust authentication and an owner role solely for disposable tests, not operational storage. Journal triggers and hashes do not defend against a database administrator recomputing the entire chain and head; external signed anchors and least-privilege deployment remain required future decisions. Full-history verification on append/replay favors correctness over large-history performance. Redaction protects configured application handlers and boundaries, not intentional raw secret extraction by arbitrary code. No credentials or strategy content are placed in test snapshots.

## Exact reproduction commands

Run in the repository root using PowerShell; PostgreSQL 17 binaries must be installed at the path documented in [README.md](README.md).

```powershell
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
uv python install 3.12
uv sync --locked
.\scripts\postgres_sandbox.ps1 -Action Start
$env:TE_TEST_DATABASE_URL = 'postgresql+psycopg://phase1_test@127.0.0.1:55439/postgres'
.\scripts\verify.ps1
$env:PRE_COMMIT_HOME = Join-Path (Get-Location) '.cache\pre-commit'
uv run --locked pre-commit install
$phase1Files = @(git ls-files --cached --others --exclude-standard)
uv run --locked pre-commit run --files @phase1Files
.\scripts\postgres_sandbox.ps1 -Action Stop
```

`verify.ps1` executes locked dependency sync, the complete pytest suite (including a fresh CLI migration), Ruff lint and format checks, strict mypy, secret scanning and Git whitespace checks, aborting on any failure. For a separately provisioned empty development database, privately set TE_DATABASE_URL and run `uv run --locked alembic upgrade head`. Never point the integration maintenance URL at a nonlocal or operational database.

Stop after Phase 1. Phase 2 has not begun.
