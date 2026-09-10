# ADR-001: Phase 1 runtime and event storage

Status: accepted development baseline by owner instruction following G0 approval; implementation decisions below apply to Phase 1 only. The authoritative specification tag is `spec-v0.1.0`; the tagged specifications are unchanged by this implementation.

## Decisions

- Windows 11 development host; Python 3.12 with uv-managed environment and committed `uv.lock`. Pydantic provides frozen, extra-field-forbidden boundary models. Python minor version is constrained to 3.12; exact dependencies are locked.
- PostgreSQL operational event storage, SQLAlchemy 2 Core for explicit transaction control, and Alembic for schema migrations. Only account heads and journal events are introduced. Tests use PostgreSQL 17, not an in-memory substitute.
- SQLite is not selected for operational events: the journal relies on PostgreSQL row locking, concurrent account serialization, transactional constraints and trigger behavior. Testing SQLite would not validate these properties. SQLite is not used as a test fallback.
- Decimal contract `decimal34-half-even-v1`: fresh local precision-34/ROUND_HALF_EVEN context, no binary float input, explicit tick floor/ceiling/nearest and lot-step floor. Boundary routines use exact integer ratios derived from Decimal to avoid rounding across a valid tick. Amounts require explicit units; 34-digit/exponent-100 input limits bound serialization. No indicator or trading arithmetic is implemented.
- UTC normalization at contract boundaries; reject naive datetimes. Store UTC text at microsecond precision in event envelopes, with ordered numeric sequence columns. UUID entity/account/correlation/causation identities; signed 64-bit positive account sequences.
- Canonical contract `tagged-json-v1`: sorted string-key maps, ordered lists, distinct scalar type tags, normalized exact Decimal text, and normalized UTC timestamp text. Immutable payload text is validated on construction. SHA-256 payload and full-envelope hashes form the chain; genesis previous hash is 64 zero characters. Schema version 1 binds this representation. No mutable nested payload reference is retained.
- Caller controls outer transaction. Per-account head lock serializes writers; a savepoint contains each append. A duplicate ID with identical complete draft is idempotent, conflicting content fails. Global event-ID uniqueness also prevents reuse across accounts. Replay locks the head and verifies the entire chain and head anchor; append verifies existing history before extension. This favors audit correctness over throughput at Phase 1 scale.
- Database triggers prohibit historical UPDATE/DELETE/TRUNCATE. No mutation/deletion API or destructive migration downgrade exists. Owner/superuser trigger bypass is used only in a disposable test corruption fixture and rolled back. Hashes detect corruption against retained history/head; they do not authenticate history against an administrator who rewrites every hash and anchor. External signed checkpoints and operational role separation remain future D05 work.
- Immutable configuration defaults to entries disabled and accepts no entry-enabling value. RuntimeMode has exactly the five specified values and no LIVE mode. The entry permission implementation always returns disabled. These are contracts, not executable paper/demo services.
- Parquet preparation is an immutable artifact/store protocol only. No pyarrow dependency, ingestion, broker dependency, network client for markets, strategy, risk engine, simulator or UI is introduced.

## Verification and consequences

pytest and Hypothesis cover primitive validation, Decimal boundaries, canonicalization, secrets, transaction/replay invariants and scope. Integration fixtures create a fresh PostgreSQL database and run the actual Alembic CLI. Concurrent appends and duplicate races use separate connections. Ruff, strict mypy, detect-secrets and local pre-commit hooks form the quality baseline. See [PHASE1_REPORT.md](../PHASE1_REPORT.md) for executed evidence.

Replay and append currently inspect the complete account history; large-history performance optimization requires separate evidence and is not hidden behind an unverified cache. Configuration has no automatic `.env` loading or log-producing startup service. Consumers must use the safe logging filter and restricted database privileges; generic infrastructure cannot prevent an intentional caller from manually revealing a secret.

## Remaining D05 decisions

The owner has resolved the development OS, Python, manager, core validation/persistence stack and quality tools. Still unresolved: deployment topology and runtime service ownership, identity provider, approved production secret facility, least-privilege database roles and migration role separation, TLS policy, backup/restore targets and drills, retention approval, external audit anchors, workload/SLO targets, CI enforcement and operational monitoring. None is implicitly approved for demo execution by passing Phase 1. Other D01–D08 phase blockers remain recorded in [PRODUCT_SPEC.md](PRODUCT_SPEC.md).
