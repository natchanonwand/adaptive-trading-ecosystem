# Phase 4A — MT5 Read-Only Bridge & Broker Validation

The bridge observes the terminal already logged in on this Windows workstation.
It has no credentials, account-selection, trading, modification, calculation or
execution API. DEMO and USD are required; real, contest, unknown and non-USD
accounts are refused. USD is an explicit current dashboard/domain limitation.

## Architecture

`mt5/client.py` reuses the existing frozen `discovery/sdk.py` lazy native loader.
That remains the sole MetaTrader5 import in the repository. The new adapter
borrows its SDK handle and exposes only initialize/shutdown, terminal/account,
symbol metadata/ticks, positions/orders and deal/order history. Native records
are copied through field allowlists; native error text never escapes, only an
integer error code. None means failure; an empty tuple means a successful empty
result. The deterministic fake requires no terminal or Windows SDK import.

Flow: native read client -> normalization -> transactional bridge store plus
Monitoring Core journal -> existing projections/API/SSE -> dashboard. No browser
talks to MT5. No accounting, strategy, risk-engine or execution semantics change.

`mt5_readonly` is a separate additive PostgreSQL schema. `install()` validates
the existing monitoring schema then idempotently creates version-1 checkpoint
and observation tables. No old migration or operational/public table changes.
Checkpoint schema version and body hashes are checked on every transaction.
Observation versions are immutable, keyed by account stream, record kind,
broker identity and body hash. A scope checkpoint row lock serializes writers.
One observer process per account is the operational recommendation.

Account scope is a deterministic UUID derived from broker company/server/login;
the login is never persisted or logged. This is local pseudonymization, not a
claim of anonymity. Broker tickets are unique only within account scope and
record kind. Positions preserve identifier and ticket; a netting reversal or
ticket/side transition starts a new observed lifecycle generation. Unknown
broker symbols retain their exact spelling; explicit aliases are never guessed.
EA magic, comment and provenance remain observations, not inferred attribution.
Credential-like comments are redacted. Source ADAPTER means observed/unknown
strategy attribution, not a claim that the system originated the trade.

## Explicit Monitoring integration changes

The prior account contract required lifetime realized P&L, commissions and
financing, which `account_info()` does not supply. These fields now accept null
for incomplete accounts; complete accounts still require reported totals.
Portfolio reserved risk/count also accept null. No zero is fabricated. Existing
populated event serialization and hashes are unchanged. Position symbols accept
an explicit label as well as the original enum, so external instruments survive.
The domain Asset enum, frozen risk/accounting contracts and policies are unchanged.

The additive `EXTERNAL_OBSERVATION` event carries an ActivityView with observation
status, canonical body hash and scoped reference/ticket where applicable. Full
sanitized broker facts reside in the bridge observation table under that hash.
This covers pending-order sets, sampled quotes, metadata and deals without
mislabeling them as executions or position fills. The frontend subscribes to this
additional named SSE event. Existing 26 event types remain unchanged.

The dashboard adds a Used margin card. Account/portfolio/positions are normal
Monitoring Core projections, including the broker-reported open position count.
Risk state and unsupported P&L/DD metrics remain unavailable. Imported deals are
not converted into synthetic closed-trade episodes or double-counted into P&L.
Trade/calendar reconstruction and EA behavior inference are outside this phase.

## Polling, freshness and recovery

Default cadence: account/positions/orders/selected quotes one second, health
five seconds, history ten seconds, metadata five minutes. The loop sleeps one
second between cycles; actual cycle duration also includes SDK/database work.
Only meaningful account/position/order changes emit snapshots. Unchanged quotes
deduplicate; sampled changed quotes are observations, not an all-tick recorder.
Broker/account freshness heartbeats continue even when financial values do not
change. Quote source age over 30 seconds is stale; a five-second future tolerance
accommodates call duration/clock skew, with larger future timestamps rejected.

Connection states include DISCONNECTED, CONNECTING, CONNECTED, STALE, ERROR and
SHUTTING_DOWN. A failed cycle rolls back its observations and checkpoint; a
separate health transaction marks the broker disconnected and prior account
values stale. Retry starts at two seconds, doubles and caps at 30 seconds.
Every cycle rechecks account mode/scope. An account switch reconnects into a new
scope; a switch to real/unknown refuses qualification before financial ingestion.
Shutdown persists disconnected health, stops API threads, calls SDK shutdown
and disposes database resources. Unexpected SQL/native failures are not printed
with connection/account details.

History starts at a configured recent window, then resumes from durable scanned
time minus 120 seconds, not last timestamp plus one. Broker `(time, time_msc,
ticket)` high-water identity is retained separately. Queries advance in bounded
windows and cap records; a cap/error does not advance the checkpoint. Duplicate
deals deduplicate by scoped ticket; changed facts under an existing deal identity
fail closed. Same-time tickets and late arrivals inside the overlap are covered.
Deals, checkpoints and journal events commit atomically. A crash gap is traversed
from the previous scan boundary. Backfill beyond the chosen initial window, or
broker corrections/late arrivals older than overlap, require explicit review;
this is not a claim of unlimited history completeness.

Each successful position poll compares the previous broker observation with the
projection. Missing or mismatching read-model values emit reconciliation mismatch
and rebuild from the authoritative journal, then apply the latest broker set.
Missing broker positions close only after a successful positions read. Their
final P&L/exit price remain unknown. Hash corruption is an integrity error, not
silently overwritten. No synthetic fill/accounting posting is generated.

## Economics

`BrokerInstrumentSnapshot` preserves tick sizes/values, contract/lot limits,
digits/point, stop/freeze levels, currencies, margin-related fields and mode.
Statuses are PARTIAL/INVALID/UNAVAILABLE unless independently qualified. Current
metadata-only broker snapshots remain PARTIAL and `sizing_eligible=false`.
`margin_initial=0` does not mean zero required margin. Margin and commission
costs are not inferred from leverage or account totals.

`to_economics()` adapts to the unchanged Phase 3.4 `Economics` contract only with
separately reviewed `ValidatedCosts` and compatible linear USD metadata. It
rejects missing/invalid economics and absent cost evidence. The real runner never
calls this adapter for sizing. Neither profit/margin calculation APIs nor trading
APIs are called. Observed broker economics are documented in the phase report
and `reports/mt5_broker_economics.json`.

## Startup

Use the existing Python 3.12/uv environment and optional `discovery` dependency;
no new Python/npm dependencies are added. MT5 must already be logged into DEMO.
Set `TE_DATABASE_URL` to a local monitoring database without echoing credentials.

```powershell
uv sync --locked --extra discovery
uv run --locked alembic upgrade head
uv run --locked alembic -c alembic-monitoring.ini upgrade head
.\scripts\start_mt5_monitor.ps1 -Config config/mt5_readonly.example.json
```

The example mapping was checked against the observed terminal but is not an
automatic alias resolver. Review it for a different broker/terminal. Local custom
configuration belongs under `.local/`, never with credentials in Git.

In another terminal:

```powershell
cd dashboard
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` without `?mock=1`. The runner serves the same local
Dashboard API on port 8765; do not start a second API on that port. Both services
bind loopback. Ctrl+C stops the observer gracefully. `--seconds N --evidence
.local/phase4_a/new-report.json` supports a bounded local smoke run; evidence
files are created exclusively and never overwritten.

## Verification and limitations

Set the disposable local `TE_TEST_DATABASE_URL` and run:

```powershell
.\scripts\verify_phase4_a.ps1
```

The gate checks checkpoint `6147c75`, allows only the enumerated integration
changes, then composes the original Phase 3.6 gate through all prior gates and
874-file evidence comparison. The old pre-3.6 local hash manifest is preserved;
an explicit current-phase manifest parameter protects all 46 prior working files
during execution. Scope tests still compare every original frozen tag path.
The accounting scope guard was corrected for newly tracked later-phase files,
while frozen file edits/deletions remain forbidden. No old assertion about
domain behavior, trade prohibition or evidence integrity was relaxed.

Synthetic tests and a real-demo smoke are separate evidence. Installed Chrome
checks actual API/SSE-backed pages without mock data. No trade is opened for
coverage; live position changes and pending orders can be tested using fakes.

The inherited journal replays the chain on append. Long-running/high-volume
capacity and observation retention require review; the short smoke is not a
load qualification. The history API materializes each bounded native window
before its record cap can be checked. Broker metadata is a current snapshot,
not historical economics or sizing approval. No Phase 4B path is selected here.

Official API semantics consulted: [history_deals_get](https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py)
documents named-tuple results, time-window queries and None/error handling.
