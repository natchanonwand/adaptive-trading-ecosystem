# Phase 3.5 — Monitoring Core & Telemetry Foundation

## Boundary and authority

The monitoring package observes values; it cannot place, size, reserve, cancel or
flatten orders. Phase 3.4 accounting, portfolio and Risk Engine remain authoritative.
Their code, tests and reports are unchanged. V0 and experimental HR policies are
unchanged. Health observations never call the risk state machine.

```
Phase 3.4 snapshot / decision or validated external observation
  -> typed telemetry envelope
  -> TelemetryJournal.append (caller-owned PostgreSQL transaction)
  -> immutable telemetry_events + transactional projections
  -> local GET API / durable-cursor SSE
```

This is a producer contract and monitoring foundation, not an automatic broker
collector. Existing backtests and frozen research evidence are not rewritten to
emit telemetry. Producers explicitly construct and append observations. External
EA transport and authenticated ingestion remain future work.

The operational journal remains unchanged. Telemetry has its own source records;
it does not replace the operational journal or write a second operational event.
`domain_identity`, `correlation_id`, `causation_id` and immutable payloads retain
lineage. The producer owns account, strategy and symbol attribution and must use
the identifiers of the authoritative snapshot/decision. A supplied identity is a
reference, not independent proof of an external EA's financial claims.

## Contracts and ordering

The 26 `EventType` members cover account/portfolio, position lifecycle, intent,
risk, broker/reconciliation, strategy/EA and system/execution incident observations.
Schema version 1 uses a discriminated, immutable payload. Decimal values serialize
as strings; binary floats are rejected for money. Times must be timezone-aware and
are normalized to UTC. Unknown financial values are null, never invented zeros.

Envelope metadata includes `event_id`, type/version, occurred/recorded times,
source/source_instance_id, `scope` (environment/run_id/account_id), strategy_id,
symbol, correlation_id, optional causation/correction, and external EA magic,
comment and ticket. Strategy attribution may be absent for external positions.
Free text is untrusted data, serialized as JSON and never logged by the API.

Environment is BACKTEST, PAPER_FORWARD, DEMO or LIVE. LIVE is strictly read-only
external/adapter/system observation; DOMAIN events in LIVE are rejected. The
execution `RuntimeMode` enum is unchanged and has no LIVE capability.

* Stream identity hashes environment + run + account. Sources do not share a
  sequence counter, and streams never combine environments or runs.
* Event identity hashes stream + source_instance + source_sequence. Sequence starts
  at 1 and is contiguous per source. Preserve the original recorded time and body
  on retries. Identical delivery is a no-op; changed content for the same identity
  is a conflict, not an overwrite.
* PostgreSQL stream-head locking assigns a contiguous stream sequence. Concurrent
  duplicate appends serialize. This is arrival order across sources; it does not
  claim global event-time ordering. Occurred time must not regress within a source
  or a projected entity. Source identity cannot change under an existing instance.
* Invalid order, identity, lineage or corrupted prior projection fails the append
  savepoint, including its journal record and head updates. Nothing is silently
  applied or dropped. There is no automatic reordering buffer/quarantine in v1;
  callers retain failed deliveries and retry in order or investigate corruption.
* Corrections append a new delivery referring to a prior event in the same stream,
  source, event type and attributed entity. Existing raw bytes never change.
  Position lineage cannot change and a closed episode cannot reopen.

Each stored record includes previous hash and canonical content hash. Full replay
checks identity, hash chain, duplicated SQL columns, source order and both head
tables. Append performs a full verified replay under the stream lock. This favors
auditability over throughput and is intentionally not a raw-tick firehose.

## PostgreSQL and replay

Migration `0001_telemetry` is an additive Alembic lineage under
`migrations/monitoring`, using the existing Alembic/SQLAlchemy/environment conventions.
The frozen integration regression pins both the public table set and its exact
`0001_journal` head, so telemetry owns `monitoring.alembic_version` instead of
changing the operational version table or weakening that regression. Run:

```powershell
uv run --locked alembic upgrade head
uv run --locked alembic -c alembic-monitoring.ini upgrade head
```

Use an explicitly configured development database. The monitoring environment
checks that the required operational baseline exists first; repeated upgrade is
idempotent. All new tables and the append-only function live in the `monitoring`
schema. The public schema and its revision remain exactly the existing baseline.
SQLAlchemy explicitly qualifies monitoring objects; no search_path change is
needed. Existing operational tables are preserved. No new packages are needed.

| Table | Purpose |
|---|---|
| telemetry_events | Append-only canonical source record; delivery/event uniqueness |
| telemetry_heads / telemetry_source_heads | Serialized stream and source cursors |
| account_snapshots / portfolio_snapshots | Historical authoritative valuations |
| position_projection | Latest position state per episode, including closed state |
| risk_projection | Latest account risk, last rejection and state-change time |
| system_health_projection | Component state per source instance |
| trade_projection | Completed episode summaries, nullable when not supplied |
| activity_projection | Strategy/source status and supplied summary metrics |

PostgreSQL denies UPDATE, DELETE and TRUNCATE on raw telemetry. No automatic raw
retention or destructive downgrade exists. Administrative table-owner privileges
are not a cryptographic trust boundary; production DB roles/backups remain future
operations work. Projections have content hashes and can be discarded and rebuilt.

```python
from trading_ecosystem.monitoring.journal import TelemetryJournal

# event is a validated TelemetryEvent built with create_event(EventInput(...)).
with engine.begin() as connection:
    stored = TelemetryJournal(connection).append(event)

with engine.begin() as connection:
    journal = TelemetryJournal(connection)
    verified_records = journal.replay(event.scope.stream_id)
    rebuilt_count = journal.rebuild(event.scope.stream_id)
```

Outer transaction ownership belongs to the caller: commit publishes both raw
record and projection; rollback publishes neither. Rebuild locks the stream,
verifies all raw records, deletes only its derived rows and reprojects atomically.
It preserves other streams and all raw records. Replay into empty projection
tables must reproduce all values and hashes exactly. Full replay is the explicit
audit operation; bounded API event reads check their page and preceding hash
anchor, not the entire journal on every poll.

## Authoritative values and future queries

`adapters.account_view`, `portfolio_view`, `position_view` and `risk_view` copy
Phase 3.4 snapshots/decisions. There is no second financial arithmetic kernel.
Risk adapter rejects a decision paired with a different snapshot. Portfolio risk
state remains null unless supplied with the matching account's domain RiskState.

Portfolio includes account balance/equity/realized/unrealized PNL, margin,
exposure, open/reserved risk, UTC daily PNL, peak NAV, drawdown and position counts.
The source domain tracks flow-adjusted peak NAV, not raw peak equity:
`peak_equity` is null rather than relabeling NAV. Position realized PNL and take
profit are null unless authoritative per-episode values are supplied. LONG marks
use bid; SHORT marks use ask, matching the domain snapshot.

Amounts/exposure/open-risk are USD under the existing domain model. Policy limits
`risk_per_trade`, `portfolio_risk_limit`, `daily_loss_limit`, `drawdown_limit` and
`daily_loss`/`drawdown` are fractions, not percentages or dollar amounts. `peak_nav`
uses the domain's flow-adjusted NAV units. Consumers must preserve these units.
Risk projections retain the last rejection reason across later approvals and the
time of the last observed state transition (ACTIVE/PAUSE_ENTRIES/HALT_AND_FLATTEN).

TradeView retains UTC close time, gross/net PNL, net R, commission, financing,
spread cost, outcome and completeness. A close without a supplied trade summary
still creates a trade row with unknown metrics and `complete=false`. No inference
of net R or transaction costs is made from incomplete position data. Historical
account/portfolio snapshots plus per-trade rows allow future UTC daily grouping,
wins/losses/trade counts and sampled intraday drawdown; exact unobserved extrema
cannot be reconstructed. This phase does not invent a calendar aggregation API.

Activity rows support strategy/source status, trades, PNL, net R and drawdown,
with occurred time as last activity. BTCUSD, XAUUSD and USTEC100 attribution remains
available in position/trade/event data. Unknown or unreported health is absent,
not automatically HEALTHY. Health age is observable via occurred_at; producers
must emit STALE observations. A wall-clock expiry policy is not invented here.

## Local API and realtime

```powershell
# Set TE_DATABASE_URL using the existing local secret/configuration mechanism.
uv run --locked python -m trading_ecosystem.monitoring --port 8765
```

The frozen scope tests prohibit FastAPI, so the minimal API uses the Python stdlib
ThreadingHTTPServer instead of changing frozen tests or dependency pins. It binds
only 127.0.0.1. No CORS; Origin-bearing requests and unexpected Host headers are
rejected. This unauthenticated local development server is not a production or
multi-user deployment. No frontend is included.

| Endpoint | Result |
|---|---|
| GET /health | Database connectivity health; 503 on DB failure |
| GET /api/v1/account | Latest account snapshot |
| GET /api/v1/portfolio | Latest portfolio snapshot |
| GET /api/v1/positions | Current episode states, including closed episodes |
| GET /api/v1/trades | Completed episode summaries |
| GET /api/v1/risk | Latest account risk observation |
| GET /api/v1/events | Ordered, bounded canonical journal records |
| GET /api/v1/system | Observed component/source health states |
| GET /api/v1/activity | Strategy/source activity and supplied metrics |
| GET /api/v1/stream | Read-only SSE of committed canonical records |

All `/api/v1` endpoints require `stream_id=<UUID>` (obtain from producer Scope).
`after` is a nonnegative stream-sequence cursor, default 0; `limit` is 1..1000,
default 100. Duplicate/unknown query keys reject with 400. Unknown routes return
404; POST/PUT/PATCH/DELETE return 405. Corruption/database errors return a generic
503 without SQL/credentials. JSON responses include `read_only`, items and cursor.
Single-state endpoints return the latest newer row; collection endpoints page
ascending by sequence. Projection cursors describe latest states, not a historical
event stream; use `/events` or SSE when every transition is needed.

SSE example:
`/api/v1/stream?stream_id=<UUID>&after=0&limit=100&follow=true`.
Each frame has `id` (stream sequence), `event` (type), and `data` (canonical stored
record). Connections poll committed PostgreSQL rows every second. Empty polls
send heartbeat comments. `follow=false` returns one bounded page and closes.
Reconnect with Last-Event-ID; explicit `after` takes precedence. Cursors belong
to one stream. On data failure the connection sends `monitoring_error` and closes.
There is no in-memory event bus or broker to lose messages across API restarts.
Clients should apply events idempotently: connection failure can leave delivery
acknowledgement ambiguous even though journal insertion itself is idempotent.

## Verification and limits

Set the existing disposable local `TE_TEST_DATABASE_URL`, put uv on PATH, then run:

```powershell
.\scripts\verify_phase3_5.ps1 -CodeOnly
.\scripts\verify_phase3_5.ps1
```

Full verification delegates to the unchanged Phase 3.4 gate: full tests including
fresh PostgreSQL migrations and real localhost HTTP/SSE, Ruff/format/strict mypy,
secret scan, Phase 2B real datasets, Phase 3.3B research and Phase 3.3C portfolio
verification, plus 874 evidence file hashes before/after. It separately hashes
the 24 Phase 3.4 working files and requires zero skipped tests. Test XML is copied
to `test-results/phase3_5.xml` (ignored generated evidence).

No automatic collector, broker execution, frontend, GPT call, optimization, cloud
service, distributed ordering, tick streaming or compaction is included. Schema
version evolution, production authentication/roles, process-level backpressure,
high-volume append optimization and calendar presentation remain future work.
Stop before Phase 3.6 Dashboard.
