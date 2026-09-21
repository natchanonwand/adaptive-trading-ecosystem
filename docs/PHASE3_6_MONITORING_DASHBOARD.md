# Phase 3.6 — Local Monitoring Dashboard

Read-only React/TypeScript/Vite UI above the existing PostgreSQL Monitoring Core.
The six pages are Overview, Portfolio, Trades, Risk, Systems and Research.
Risk/accounting remain authoritative in the Python domain; the browser formats
reported facts and never sizes orders or calculates research qualification.

## Architecture and API

`dashboard/` contains the independent frontend. `dashboard_api/` extends the
existing standard-library MonitoringServer without modifying Phase 3.5 files.
The original `/health`, `/api/v1/account`, `portfolio`, `positions`, `trades`,
`risk`, `events`, `system`, `activity`, and `/api/v1/stream` remain available.

New GET `/api/v1/dashboard/` routes:

| Route | Purpose |
| --- | --- |
| streams | Bounded stream catalog with scope/environment and cursor pagination |
| snapshot | Consistent views, head cursor and last 30 events |
| history | Latest bounded account snapshots for balance/equity |
| positions | Open positions, server filters and cursor pagination |
| trades | Reported closed trades, server filters and cursor pagination |
| calendar | UTC daily sums of reported closed-trade facts |

Queries use a repeatable-read, read-only transaction and UTC session timezone.
Stored projection hashes are checked. Snapshot view errors are isolated so a
bad optional view does not erase a valid account summary. API dates are UTC;
money remains decimal strings. Unknown is null, never a fabricated zero.
POST, PUT, PATCH and DELETE remain rejected. Host/origin checks are inherited.

Pages request bounded results (50 trades/positions, 200 history samples).
The API caps collection requests at 500, date filters at 366 days, calendar
windows at 31 days and calendar input at 10,000 trades. Over-cap calendar
responses explicitly report partial coverage and do not present truncated sums.
Position sort/filter applies to the displayed page; server symbol/strategy/
environment/date filters and continuation cursors support larger collections.

Calendar aggregation uses backend Decimal sums of existing net/gross P&L, R,
commission, financing and spread facts. If any constituent metric is unknown,
that metric's daily sum is unknown. Unobserved days are unknown, not zero.
These are observed closed-trade totals, not account daily P&L or a reconstructed
ledger. Intraday drawdown is unavailable. Overview daily P&L comes from the
authoritative account projection instead.

## Realtime and presentation semantics

The UI loads an atomic snapshot and subscribes to the existing 26 named SSE
event types from its head cursor. Events invalidate views, with a one-second
refresh debounce; pending invalidations survive an in-flight refresh. No
browser financial event reducer is introduced. Duplicates are ignored;
noncontiguous sequences and malformed events stop the subscription and expose
an error requiring a fresh snapshot. Reconnect waits two seconds and creates a
new EventSource with the latest cursor because the backend explicit `after`
query takes precedence over Last-Event-ID. Browser refresh obtains a new
snapshot; local storage retains only stream selection.

Connection becomes STALE after 30 seconds without fresh source telemetry,
using backend recorded timestamps rather than receipt time. Transport failures
show DISCONNECTED. Account stale flags are also visible. Each resource has its
own loading/error/no-data state; failures never silently activate mock data.

The SVG chart uses authoritative snapshots, keyboard sample inspection and
tooltips. Null samples and intervals over five minutes break the line. This is
a documented UI gap threshold, not a market-session or accounting inference.
Display formatting uses decimal-string/BigInt rounding, preserving null versus
zero and avoiding binary float rounding for money. Chart geometry alone uses
numeric conversion. UTC timestamps and metric units are explicit.

Unavailable Phase 3.5 facts remain unavailable: peak drawdown, maximum position
count, per-position risk, actual trade exit fill, original traded quantity and
research win rate. Closed-position remaining quantity zero is not traded
quantity; its mark price is not an exit fill. External EA source, magic number,
instance, strategy and broker ticket are optional metadata.

## Local startup

Prerequisites: local PostgreSQL, Python/uv as configured by the repository,
Node 22.13+ (tested 22.13.0) and npm (tested 10.9.2). Set `TE_DATABASE_URL` through
the existing local configuration; do not put credentials in frontend files.

Terminal 1, from the repository:

```powershell
uv run --locked alembic upgrade head
uv run --locked alembic -c alembic-monitoring.ini upgrade head
uv run --locked python -m trading_ecosystem.dashboard_api --port 8765
```

Terminal 2:

```powershell
cd dashboard
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. Production artifact review uses `npm run build`
then `npm run preview`. Both Vite modes bind loopback and proxy to loopback
port 8765. Only the exact local UI origins on port 5173 are removed by the
proxy; foreign origins remain subject to backend rejection. This is a trusted
local workstation tool, not an authenticated public deployment.

Explicit `?mock=1` selects synthetic development fixtures and shows a persistent
MOCK DATA banner. Default runtime uses real telemetry. A fresh database can be
empty: this phase does not ingest MT5 data or invent account history.

## Verification

Set `TE_TEST_DATABASE_URL` to the disposable PostgreSQL test server, then run:

```powershell
.\scripts\verify_phase3_6.ps1
```

This performs locked npm installation, strict TypeScript, ESLint, Prettier,
Vitest, production build, and the unchanged Phase 3.5 full verifier composition.
That composition includes the complete Python/PostgreSQL suite, Ruff, format,
strict mypy, secret scan, registry, Phase 2B real datasets, Phase 3.3B research,
Phase 3.3C portfolios and byte comparisons of frozen evidence. The new verifier
also compares the 46 preserved Phase 3.4/3.5 working files before and after;
when present, the pre-implementation local hash capture is checked as well.
`-CodeOnly` explicitly excludes historical evidence and is not final acceptance.

Frontend tests cover formatting/nulls, API failures/timeouts/malformed data,
components, environments, risk states, SSE ordering/reconnect and hook refresh
behavior. PostgreSQL integration tests exercise real queries and the actual
TypeScript client against the running fixture HTTP/SSE server. Installed Chrome
is used for local visual review; no browser automation dependency was added.

## Scope and limitations

Only React and React DOM are runtime dependencies. Tooling is pinned in the npm
lockfile; no chart/component/state framework is required. No Python dependency
was added. The retro theme uses readable body text, monospaced financial values,
semantic navigation, visible focus, text status labels and reduced motion.

History is a bounded latest window, not a full historical analytics explorer.
Calendar completeness depends on telemetry supplied to the selected stream.
SSE invalidation queries are bounded but API pressure should be reviewed with
actual telemetry cadence before the next phase. Screenshots use conspicuous
mock data and do not constitute live trading evidence. There are no execution
controls, MT5 bridge, GPT analysis, qualification decisions or cloud deployment.
Stop after this phase for UI, query pressure and telemetry-gap review.
