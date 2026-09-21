# PHASE 3.5 — MONITORING CORE

Status: **PASS — complete code and historical-evidence gate, exit code 0.**
Repository: `C:\Trading\adaptive-trading-ecosystem`.
Verification started 2026-09-16; final report reviewed 2026-09-17 (Asia/Bangkok).

| Capability | Result |
|---|---|
| Event contracts — 26 types, immutable v1, canonical identity/UTC/Decimal | PASS |
| Durable journal — PostgreSQL append-only triggers, transactional projections | PASS |
| Idempotency — identical retry/concurrent retry, conflicting content rejected | PASS |
| Replay — empty projections rebuilt identically, hashes/heads verified | PASS |
| Portfolio projection — authoritative LONG/SHORT, partial close, multiple assets | PASS |
| Risk projection — ACTIVE / PAUSE_ENTRIES / HALT_AND_FLATTEN and rejection history | PASS |
| System health — all required components and five health states | PASS |
| API — local GET endpoints, query validation, read-only methods, generic errors | PASS |
| Realtime stream — committed publication, reconnect, cursor deduplication | PASS |
| External EA compatibility — optional internal strategy, magic/comment/ticket, LIVE observation | PASS |

| Verification | Result |
|---|---|
| Existing tests | 646 passed |
| New contract/scope tests | 48 passed |
| New PostgreSQL/API/SSE tests | 61 passed |
| New tests total | 109 passed |
| Total | **755 passed, zero failures/errors/skips** |
| Ruff | PASS |
| Ruff format | PASS — 164 files |
| Strict mypy | PASS — 136 source files |
| Secret scan | PASS — 188 project files, including final report |
| PostgreSQL | PASS — 73 integration tests total, fresh DB and both migrations |
| Phase 2B real dataset verification | PASS — BTCUSD 36036 / USTEC100 23977 / XAUUSD 33647 bars |
| Phase 3.3B research evidence verification | PASS — 12 results, identities, split boundaries, exact report |
| Phase 3.3C portfolio evidence verification | PASS — four R-space and four synthetic results, replay/report |
| Phase 3.4 full verification | PASS |
| Frozen dataset/research evidence — 874 files | PASS — identical file set and bytes before/after |
| Preserved Phase 3.4 working files — 24 files | PASS — identical SHA-256 before/after full gate |
| Tagged Phase 3.3C tracked baseline | PASS — zero tracked changes |

Code gate: `.\scripts\verify_phase3_5.ps1 -CodeOnly`.
Full gate: `.\scripts\verify_phase3_5.ps1` — PASS, exit code 0.
Machine-readable tests: `test-results/phase3_5.xml`.
Full execution log: `test-results/phase3_5-full-gate.log`.
Generated test/log evidence is Git-ignored; no historical simulation is regenerated.
The Phase 2B and Phase 3.3B full-suite invocations both passed all 755 tests.
Verified historical runs: `phase3_3b-e0a03fae2bf50aadd651586b` and
`phase3_3c-a78142064358de1978b2c420`; dataset run
`20260911T161046Z-ee75c598`. The retained failed dataset run is included in the
874-file unchanged-evidence comparison.

## Files added — 22

- alembic-monitoring.ini
- migrations/monitoring/__init__.py
- migrations/monitoring/env.py
- migrations/monitoring/script.py.mako
- migrations/monitoring/versions/0001_telemetry.py
- src/trading_ecosystem/monitoring/__init__.py
- src/trading_ecosystem/monitoring/__main__.py
- src/trading_ecosystem/monitoring/adapters.py
- src/trading_ecosystem/monitoring/api.py
- src/trading_ecosystem/monitoring/contracts.py
- src/trading_ecosystem/monitoring/journal.py
- src/trading_ecosystem/monitoring/projections.py
- src/trading_ecosystem/monitoring/queries.py
- src/trading_ecosystem/monitoring/schema.py
- tests/monitoring/__init__.py
- tests/monitoring/fixtures.py
- tests/monitoring/test_contracts.py
- tests/monitoring/test_scope.py
- tests/integration/test_monitoring.py
- scripts/verify_phase3_5.ps1
- docs/PHASE3_5_MONITORING_CORE.md
- PHASE3_5_REPORT.md

## Files modified

None of the pre-existing files. All 24 Phase 3.4 working files, frozen tagged
components, dependency pins, lockfile and prior verifier/test source remain intact.
The new Phase 3.5 files remain untracked for review, alongside the preserved Phase
3.4 working state. No commit, tag or push.

## Architecture decisions

1. Typed telemetry consumes Phase 3.4 values through adapters. It performs no
   independent financial arithmetic and never calls sizing, fill or execution APIs.
   V0 and the separate experimental/demo HR policy remain unchanged.
2. A telemetry-only journal is the source record for monitoring. Stream identity
   partitions environment/run/account. Per-source sequence and stream-head locks
   enforce ordering. Raw append and derived state commit together. Corrections are
   new immutable events; raw SQL UPDATE/DELETE/TRUNCATE is denied.
3. The frozen migration regression asserts the exact public table set and revision
   `0001_journal`. Monitoring therefore uses its own additive Alembic lineage and
   `monitoring` schema/version table, with the original migration required first.
   This preserves the old assertions rather than changing their expected results.
4. Frozen scope tests prohibit FastAPI. The minimal API therefore uses stdlib
   ThreadingHTTPServer on 127.0.0.1 and SSE. No dependencies or old scope tests change.
   Committed PostgreSQL cursors replace an ephemeral bus; restart/reconnect can
   reload durable observations. No Redis/Kafka or cloud infrastructure is added.
5. LIVE is a separate read-only telemetry environment, not an execution mode.
   External positions need not pretend to belong to the internal strategy engine.
6. Snapshot history and nullable trade/activity summaries preserve the inputs for
   future UTC daily calendars and EA research. Unknown financial metrics remain
   null. Peak NAV is not relabeled as peak equity. Health does not alter risk state.

## Defects found and resolved during verification

- New fixture typing/import and long-line issues were fixed in Phase 3.5 files.
- Full regression exposed the frozen public-schema/revision assertions. The new
  migration was isolated by schema and Alembic lineage; no existing test was edited.
- The additional Alembic env module needed a package marker for strict mypy; it is
  now fully type-checked, with no excluded files or relaxed settings.
- Corrupted prior projection content rejects further appends until rebuilt. Tests
  cover atomic failure, read errors, repair, correction entity lineage and attempts
  to reopen closed episodes.

## Known limitations and stopping point

This is a local development monitoring foundation, not an automatic data collector
or authenticated multi-user service. Producer attribution/domain references are
trusted inputs; external financial claims are not independently reconciled here.
No HTTP ingestion, MT5 I/O, real-money execution, GPT calls or dashboard exists.

Full-history verification on each append favors auditability over throughput.
Invalid/reordered observations fail explicitly; a durable rejection queue and
distributed reordering are not implemented. SSE polls every second, and clients
must retain per-stream cursors and apply observations idempotently.

Per-position realized PNL, net R, costs and peak equity remain null unless supplied
by an authoritative source. Historical samples cannot infer unobserved intraday
extrema. No second calendar/accounting formula is introduced. Health staleness is
producer-reported; no new wall-clock policy changes the Risk Engine. Production
authentication/roles, throughput tuning, compaction and UI remain future work.

The unchanged Phase 3.3B verifier emitted an existing Pydantic instance
`model_fields` deprecation warning. Verification passed; the frozen verifier was
not modified to suppress the warning.

The compatibility choices above are deliberate; scope is unchanged. Phase 3.5 is
complete and stopped before Phase 3.6 or any frontend implementation.
