# Phase 3.6 — Monitoring Dashboard

Status: PASS. Full `scripts/verify_phase3_6.ps1` completed on 2026-09-22
(Asia/Bangkok). Existing Phase 3.4/3.5 work and historical evidence are preserved.

## Implementation

React, strict TypeScript and Vite provide a local read-only dashboard with
Overview, Portfolio, Trades, Risk, Systems and Research. The retro styling uses
readable financial values, persistent environment/connection/risk indicators,
keyboard navigation, visible focus and reduced-motion support.

The additive `dashboard_api` package inherits the original Monitoring API/SSE
and adds bounded stream/snapshot/history/position/trade/calendar queries. It
uses PostgreSQL read-only repeatable-read transactions, verifies projection
hashes and normalizes timestamps to UTC. The calendar sums reported closed-trade
facts using Decimal on the backend; it does not reconstruct accounting.

The browser refreshes authoritative projections after ordered SSE events,
deduplicates events, reconnects from the latest cursor and flags source telemetry
older than 30 seconds. Financial fields remain decimal strings; unavailable
metrics remain null. Explicit mock mode is labeled and is never an error fallback.

## Acceptance evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend architecture and six pages | PASS | Component tests and Chrome review |
| Overview, portfolio, trades and risk | PASS | Authoritative values, unknowns, paging/filtering |
| Systems, calendar, events and research shell | PASS | Component and PostgreSQL query tests |
| SSE, reconnect, stale state and browser refresh | PASS | Protocol/client/hook tests |
| Null semantics and external EA metadata | PASS | Formatter/component tests |
| Read-only and loopback safety | PASS | HTTP method/origin tests; no execution controls |
| Frontend unit/component/API tests | 61 PASS | `test-results/phase3_6-frontend.xml` |
| Actual TypeScript client against PostgreSQL API/SSE | 2 PASS | Executed inside backend integration test |
| Strict TypeScript / ESLint / Prettier | PASS | Full-gate log |
| Production build | PASS | JS 260.39 kB (gzip 80.67); CSS 14.04 kB (gzip 4.10) |
| Backend and PostgreSQL regression | 777 PASS | 755 baseline + 22 new integration cases |
| Ruff / Ruff format / strict mypy | PASS | 171 formatted files; 141 typed source files |
| Secret scan | PASS | 223 project files; zero findings |
| Locked npm install / audit | PASS | 235 packages audited; zero vulnerabilities reported |
| Browser layout review | PASS | Six pages; no root overflow or JavaScript exceptions |
| Phase 2B / 3.3B / 3.3C / 3.4 / 3.5 full evidence | PASS | Full original verifier composition |
| Frozen evidence, 874 files | Unchanged | Final byte-for-byte before/after comparison |
| Preserved Phase 3.4/3.5 working files | 46 unchanged | Original pre-implementation hash capture |

The two TypeScript integration cases execute within one of the 777 pytest cases;
they are stated separately, not added to the Python test count. Logs and XML are
Git-ignored verification artifacts, not new research runs.

Final evidence: `test-results/phase3_6-full-gate.log`,
`test-results/phase3_6.xml`, `test-results/phase3_6-frontend.xml`.
Backend results have zero failures, errors or skips. Phase 2B readback verified
BTCUSD 36,036 bars, XAUUSD 33,647 and USTEC100 23,977. Phase 3.3B verified all
12 existing results, frozen dataset identities, split boundaries and report;
no historical simulation was rerun. Phase 3.3C verified four R-space and four
synthetic results plus replay/report. The 46 prior working files match their
pre-implementation SHA256 capture; tracked files still match the frozen
`phase3.3c-v0.1.0` baseline. No commit, tag or push was performed.

Installed-Chrome screenshot review used 1440x900, 1366x768, 1920x1080 and
768x1024. The tablet table scrolls within its panel; global status remains
visible. Review JSON: `test-results/phase3_6-browser-review.json`.

- [Overview, 1440](test-results/phase3_6-overview-1440.png)
- [Portfolio, 768](test-results/phase3_6-portfolio-768.png)
- [Trades, 1440](test-results/phase3_6-trades-1440.png)
- [Risk, 1366](test-results/phase3_6-risk-1366.png)
- [Systems, 1920](test-results/phase3_6-systems-1920.png)
- [Research, 1440](test-results/phase3_6-research-1440.png)

## Dependencies and architecture decisions

Runtime dependencies: React 19.3.0 and React DOM 19.3.0 only. No new Python
dependency and no heavy UI, chart, state-management or browser-automation stack.
Development dependencies are pinned in `dashboard/package.json` and its lockfile:
Vite 8.3.0, TypeScript 6.0.3, Vitest 5.0.1, ESLint 10.10.0, Prettier 3.9.7,
React Vite plugin, TypeScript ESLint, React hooks lint, Testing Library, jsdom
26.1.0 and Node/React type definitions. jsdom 26 supports the installed Node
22.13.0. Its transitive whatwg-encoding deprecation warning remains; no runtime
dependency was added to suppress a test-tool warning.

SSE remains the existing protocol. A fresh EventSource is created on reconnect
because explicit `after` takes precedence over Last-Event-ID. Snapshot cursor
and views share a database snapshot. SVG chart rendering avoids a chart library.
Only explicit local UI origins are translated by the loopback proxy. Source
telemetry time, not browser receipt time, determines freshness.

## Limitations and review points

- Peak drawdown, maximum positions, per-position risk, actual exit fill, original
  traded quantity, intraday calendar drawdown and research win rate remain unavailable.
- Calendar totals cover observed closed trades, not account daily P&L or proof
  of complete broker history. Unknown days/constituents are never replaced by zero.
- History is the latest 200 samples; UI chart gaps over five minutes are
  presentation semantics. Calendar processing caps at 10,000 trades per month.
- Position sorting/filtering is page-local. Trade filters and pagination run on
  the server. Feed/history/catalog/collections are bounded; invalidation refresh
  is debounced one second. Review pressure under real telemetry before Phase 4A.
- Local-only trusted-workstation deployment; no public authentication layer.
  Screenshots use visibly labeled synthetic mock data, not live account evidence.
- No MT5 bridge/execution, live controls, optimization, GPT analysis or qualification.
- The unchanged Phase 3.3B verifier emits Pydantic's instance `model_fields`
  deprecation warning. This is a future dependency-migration concern, not a
  verification failure; frozen verifier source was preserved.

## Deviations and defects resolved

The original Monitoring Core had no atomic dashboard snapshot, history/calendar
query or stream catalog. Additive read-only routes were required; old routes,
domain semantics, migrations and evidence were not changed. No Playwright
dependency was needed: installed Chrome supplied visual review screenshots.
During resume, a new component test's ambiguous text selector was scoped to the
account card because the chart legitimately displayed the same balance. Windows
locked the preview server's native Vite module during npm ci; only that project
preview was stopped before retrying the gate. Ruff also caught one overlong line
in a new pagination test; line wrapping fixed it without behavior changes.
Original tests were not weakened.

See [implementation and startup guide](docs/PHASE3_6_MONITORING_DASHBOARD.md).
Stop point: Phase 3.6 review; do not begin Phase 4A.

## Files added (35)

- `PHASE3_6_REPORT.md`
- `dashboard/.gitignore`
- `dashboard/.prettierignore`
- `dashboard/.prettierrc.json`
- `dashboard/eslint.config.js`
- `dashboard/index.html`
- `dashboard/package-lock.json`
- `dashboard/package.json`
- `dashboard/src/App.tsx`
- `dashboard/src/api.ts`
- `dashboard/src/client.ts`
- `dashboard/src/components.tsx`
- `dashboard/src/format.ts`
- `dashboard/src/hooks.ts`
- `dashboard/src/main.tsx`
- `dashboard/src/mock.ts`
- `dashboard/src/sse.ts`
- `dashboard/src/styles.css`
- `dashboard/src/types.ts`
- `dashboard/tests/api.test.ts`
- `dashboard/tests/backend.integration.ts`
- `dashboard/tests/components.test.tsx`
- `dashboard/tests/format.test.ts`
- `dashboard/tests/hooks.test.tsx`
- `dashboard/tests/setup.ts`
- `dashboard/tests/sse.test.ts`
- `dashboard/tsconfig.json`
- `dashboard/vite.config.ts`
- `docs/PHASE3_6_MONITORING_DASHBOARD.md`
- `scripts/verify_phase3_6.ps1`
- `src/trading_ecosystem/dashboard_api/__init__.py`
- `src/trading_ecosystem/dashboard_api/__main__.py`
- `src/trading_ecosystem/dashboard_api/queries.py`
- `src/trading_ecosystem/dashboard_api/server.py`
- `tests/integration/test_dashboard.py`

Files modified from the pre-Phase 3.6 state: none. Existing untracked Phase 3.4/3.5 files are preserved, not counted as new Phase 3.6 work. Generated node_modules/dist, local helper scripts, logs and screenshots are Git-ignored.
