# Phase 2A discovery report

Status: **COMPLETE — Phase 2A read-only discovery only**. Only read-only discovery is authorized; Phase 2B has not begun. Phase 1 is frozen at `phase1-v0.1.0`. This report contains owner-permitted broker metadata and sanitized observations, no account identifier or credential.

## Connected environment

- Broker company: **Exness Technologies Ltd**.
- Server: **Exness-MT5Trial14**.
- Account trade mode: **DEMO**, verified from the actual numeric account mode, not the server name.
- Account currency: **USD**.
- Identity retrieved: `2026-09-10T14:49:14.861402Z`. Run as-of: `2026-09-10T14:00:00Z`; final probe observation: `2026-09-10T14:50:44.746450Z`.
- Terminal was connected; reported Max bars: 100,000,000. This setting is not proof of broker history retention.

The provider rechecks DEMO/connection before and after reads. No login, account holder name, password or complete account record was extracted. Python bridge shutdown completed; the owner's terminal remains open. Permitted symbol selection may leave catalog candidates visible in Market Watch.

## Candidate mappings — all BLOCKED pending owner approval

No mapping is APPROVED. Prioritization for probe resources is not approval. The following are the complete seven retained candidates; the broad initial catalog pass also found Bitcoin Cash, which was excluded as a different underlying before historical probing.

| Canonical asset | Broker symbol | Description | Base / profit / margin currencies | Catalog path |
|---|---|---|---|---|
| BTCUSD | BTCUSDTm | Bitcoin vs US Dollar Tether | TET / TET / TET | `Standard\Crypto\BTCUSDTm` |
| BTCUSD | BTCUSDm | Bitcoin vs US Dollar | BTC / USD / BTC | `Standard\Crypto\BTCUSDm` |
| BTCUSD | MBTUSDm | Micro Bitcoin vs US Dollar | MBT / USD / MBT | `Standard\Forex_Indicator\MBTUSDm` |
| XAUUSD | XAUUSD247m | Gold vs US Dollar 24/7 | USD / USD / USD | `Standard\Forex\XAUUSD247m` |
| XAUUSD | XAUUSDm | Gold vs US Dollar | XAU / USD / XAU | `Standard\Forex\XAUUSDm` |
| USTEC100 | USTEC_x100m | US Tech 100 Index | USD / USD / USD | `Standard\Idx_Enlarge\USTEC_x100m` |
| USTEC100 | USTECm | US Tech 100 Index | USD / USD / USD | `Standard\Indices\USTECm` |

The plausible primary candidates are BTCUSDm, XAUUSDm and USTECm. BTCUSDTm has TET quote/profit currency; MBTUSDm has a different micro-unit price scale and instrument trade_mode=0. XAUUSD247m is a distinct 24/7 variant with different base/margin metadata and shorter history. USTEC_x100m has contract size 100, versus 1 for USTECm. None is silently substituted for the owner's canonical asset.

## Instrument metadata completeness

All seven candidates returned all 14 requested Decimal numeric fields, 10 integer fields and five description/path/currency fields: **no missing or malformed requested fields in the final snapshot**. All seven final latest quotes were positive and not crossed. A first catalog-only run saw temporarily unavailable/malformed quotes on some previously unselected symbols; the later complete run returned valid quotes. Presence of values does not validate broker semantics or historical applicability. Zero stop/freeze levels and volume limits are reported as observed, without inventing constraints.

Primary candidate numeric metadata follows; exact timestamps, currencies, descriptions, all alternative values and latest quote precision remain in ignored instrument_metadata.json.

| Field | BTCUSDm | XAUUSDm | USTECm |
|---|---|---|---|
| point | 0.01 | 0.001 | 0.01 |
| trade_tick_size | 0.01 | 0.001 | 0.01 |
| trade_tick_value | 0.01 | 0.1 | 0.01 |
| trade_tick_value_profit | 0.01 | 0.1 | 0.01 |
| trade_tick_value_loss | 0.01 | 0.1 | 0.01 |
| trade_contract_size | 1.0 | 100.0 | 1.0 |
| volume_min | 0.01 | 0.01 | 0.05 |
| volume_max | 200.0 | 200.0 | 500.0 |
| volume_step | 0.01 | 0.01 | 0.01 |
| volume_limit | 0.0 | 0.0 | 0.0 |
| swap_long | -1608.7 | -534.4 | -589.1 |
| swap_short | 0.0 | 0.0 | 0.0 |
| bid | 77318.16 | 4357.231 | 29228.09 |
| ask | 77328.16 | 4357.491 | 29229.21 |
| digits | 2 | 3 | 2 |
| trade_stops_level | 0 | 0 | 0 |
| trade_freeze_level | 0 | 0 | 0 |
| trade_calc_mode | 5 | 0 | 2 |
| trade_mode | 4 | 4 | 4 |
| trade_exemode | 2 | 2 | 2 |
| filling_mode | 3 | 3 | 3 |
| order_mode | 127 | 127 | 127 |
| swap_mode | 1 | 1 | 1 |
| swap_rollover3days | 5 | 3 | 5 |

These are current observations, not executable sizing rules or effective-dated contract history. Account DEMO mode and each instrument's numeric trade_mode are different enums and must not be confused. Commission schedules, validated margin/valuation formulas, session calendars, historical swaps and SL/TP installation semantics remain unresolved. No broker transaction was used to test them.

## H1 coverage observations

Every candidate received 7/30/90/365-day H1 requests using UTC. All 28 requests returned observations, with **zero duplicate bar timestamps, zero invalid OHLC and zero malformed timestamps**. Every latest returned bar opened at 2026-09-10T13:00:00Z. No calendar completeness or bid-price-basis claim is made.

| Candidate | 7d rows | 30d rows | 90d rows | 365d rows | Earliest in 365d request |
|---|---:|---:|---:|---:|---|
| BTCUSDm | 168 | 720 | 2160 | 8759 | 2025-09-10T14:00:00Z |
| XAUUSDm | 113 | 504 | 1462 | 5911 | 2025-09-10T14:00:00Z |
| USTECm | 111 | 502 | 1460 | 5906 | 2025-09-10T14:00:00Z |
| MBTUSDm | 168 | 720 | 2160 | 8504 | 2025-09-10T14:00:00Z |
| XAUUSD247m | 168 | 720 | 2160 | 6558 | 2025-12-11T08:00:00Z |
| USTEC_x100m | 111 | 502 | 1460 | 5906 | 2025-09-10T14:00:00Z |
| BTCUSDTm | 168 | 720 | 943 | 943 | 2026-08-02T07:00:00Z |

BTCUSDm returned 8,759 bars in a 365-day interval containing 8,760 clock hours; this is an observation for later calendar/data validation, not an automatic corruption label. Gold and index counts reflect unqualified session gaps. XAUUSD247m begins only in December 2025 in the requested year; BTCUSDTm begins in August 2026. Do not assume the terminal can provide earlier history simply because a longer range was requested.

## Tick-history probe observations

COPY_TICKS_INFO probes requested trailing 1/7/30 days plus sample days near 30/90/365 days ago. Native calls were at most one hour each. Limits: 100,000 retained ticks or 48 calls per probe and 2,000,000 retained ticks across the run. The totals include overlapping probe windows; they are not a count of unique market observations or a downloaded research dataset. Raw tick rows were not persisted.

All 2,000,000 retained observations had positive Bid/Ask and millisecond timestamps; none were crossed or malformed. There were 25,311 duplicate-timestamp excess rows aggregated within the individual probes. This count includes overlapping sampling and is not a de-duplicated global count. No source sequence ID is supplied: array order and flags are not proof of causal ordering among equal timestamps.

| Primary candidate | Requested probe | Retained ticks | Status | Duplicate timestamp excess | First / last observed UTC |
|---|---|---:|---|---:|---|
| BTCUSDm | last_1d | 100,000 | BUDGET_LIMIT | 464 | 2026-09-09T14:00:00.152000Z / 2026-09-10T10:10:54.592000Z |
| BTCUSDm | last_7d | 100,000 | BUDGET_LIMIT | 302 | 2026-09-03T14:00:00.238000Z / 2026-09-04T06:24:20.566000Z |
| BTCUSDm | last_30d | 100,000 | BUDGET_LIMIT | 181 | 2026-08-11T14:00:00.012000Z / 2026-08-12T14:19:27.692000Z |
| BTCUSDm | sample_day_30d_ago | 97,464 | OBSERVED | 176 | 2026-08-11T14:00:00.012000Z / 2026-08-12T13:59:58.891000Z |
| BTCUSDm | sample_day_90d_ago | 62,516 | OBSERVED | 240 | 2026-06-12T14:00:00.241000Z / 2026-06-13T13:59:58.308000Z |
| BTCUSDm | sample_day_365d_ago | 0 | EMPTY | 0 | none / none |
| XAUUSDm | last_1d | 100,000 | BUDGET_LIMIT | 592 | 2026-09-09T14:00:00.111000Z / 2026-09-09T18:31:32.251000Z |
| XAUUSDm | last_7d | 100,000 | BUDGET_LIMIT | 228 | 2026-09-03T14:00:00.006000Z / 2026-09-04T00:11:43.911000Z |
| XAUUSDm | last_30d | 100,000 | BUDGET_LIMIT | 601 | 2026-08-11T14:00:00.134000Z / 2026-08-12T01:26:32.661000Z |
| XAUUSDm | sample_day_30d_ago | 100,000 | BUDGET_LIMIT | 601 | 2026-08-11T14:00:00.134000Z / 2026-08-12T01:26:32.661000Z |
| XAUUSDm | sample_day_90d_ago | 100,000 | BUDGET_LIMIT | 1,002 | 2026-06-12T14:00:00.099000Z / 2026-06-12T17:52:15.796000Z |
| XAUUSDm | sample_day_365d_ago | 0 | EMPTY | 0 | none / none |
| USTECm | last_1d | 100,000 | BUDGET_LIMIT | 5,952 | 2026-09-09T14:00:00.010000Z / 2026-09-09T14:35:43.694000Z |
| USTECm | last_7d | 100,000 | BUDGET_LIMIT | 6,044 | 2026-09-03T14:00:00.048000Z / 2026-09-03T14:30:05.309000Z |
| USTECm | last_30d | 100,000 | BUDGET_LIMIT | 1,210 | 2026-08-11T14:00:00.019000Z / 2026-08-11T19:01:35.934000Z |
| USTECm | sample_day_30d_ago | 100,000 | BUDGET_LIMIT | 1,210 | 2026-08-11T14:00:00.019000Z / 2026-08-11T19:01:35.934000Z |
| USTECm | sample_day_90d_ago | 100,000 | BUDGET_LIMIT | 3,413 | 2026-06-12T14:00:00.137000Z / 2026-06-12T15:46:33.195000Z |
| USTECm | sample_day_365d_ago | 0 | EMPTY | 0 | none / none |

All three primary candidates returned zero ticks for the complete one-day sample near 365 days ago. That is a sample result, not proof of a precise retention cutoff. The 90-day samples for BTCUSDm, XAUUSDm and USTECm returned data, although gold/index samples hit the row budget. A bounded sample does not establish 12 months of usable quote replay.

Alternative probes: MBTUSDm returned 25,531 ticks for the recent day, 50,784/19,441 in request-limited 7/30-day prefixes, 10,239 in the 30-day-old sample and 16,911 in the 90-day-old sample; its 365-day sample was empty. XAUUSD247m hit 100,000 ticks in each of its first four probes; 90/365-day sample probes were empty. USTEC_x100m retained only 17,114 recent ticks before the run budget was exhausted; its remaining intervals made no native requests. BTCUSDTm tick probes were not run due to the global budget. These alternatives remain unqualified and unapproved. No additional requests were made to evade the run limit.

Every record states continuous_coverage_established=false and source_sequence_information=UNAVAILABLE. BUDGET_LIMIT or GLOBAL_BUDGET_NOT_PROBED is not EMPTY. The local artifacts distinguish the requested interval, retained first/last tick, fully processed prefix and native query count. All primary candidates received all six tick probes; incomplete alternative probing is explicitly recorded.

## Suitability by canonical asset

| Asset / primary candidate | Exploratory OHLC research | Potential quote-replay qualification |
|---|---|---|
| BTCUSD / BTCUSDm | Promising observed H1 supply; BLOCKED pending mapping approval, price-basis/calendar/cost validation | NOT QUALIFIED: recent and 90-day samples exist, year-old sample empty; full coverage, source ordering, costs and vintage metadata unresolved |
| XAUUSD / XAUUSDm | Promising observed H1 supply; BLOCKED pending mapping approval and session/bid-basis/cost validation | NOT QUALIFIED: recent/90-day samples are bounded prefixes; year-old sample empty and same-timestamp ordering unresolved |
| USTEC100 / USTECm | Promising observed H1 supply; BLOCKED pending mapping approval and contract/session/bid-basis validation | NOT QUALIFIED: high tick density exhausts budgets quickly; year-old sample empty and causal ordering unresolved |

This is discovery suitability, not G2 evidence, backtesting or trading authorization. OHLC research remains exploratory under the approved specification even after later data validation.

## Unresolved D01 and D02

D01 now has observed company/server, DEMO status, USD account currency, candidate catalog and current metadata. Still open: explicit owner mapping approval; contract-unit interpretation and effective dates; margin and tick-value reconciliation fixtures; commission/financing policy; trading calendars; filling-mode behavior; SL/TP and amendment/protection confirmation semantics. All transaction-based checks are forbidden in Phase 2A and were not attempted.

D02 still needs licensed/provider terms and retention guarantees, qualified immutable datasets, proof of bid OHLC basis, historical spread and cost schedules, time-vintage metadata, calendar-aware completeness, appropriate out-of-sample windows, and usable chronological quote ordering. The 365-day tick samples and equal-millisecond observations prevent claiming readiness for quote qualification. Increasing budgets, downloading larger history or implementing ingestion requires a separate authorized plan, not automatic Phase 2B work.

## Safety and automated verification

Final verification on 2026-09-10: **PASS**.

| Check | Result |
|---|---|
| All pytest tests | 80 passed; 0 failed/skipped; 3.96 seconds |
| Phase 1 regressions | All 56 passed, including fresh PostgreSQL migration, append/reload, tamper, rollback and concurrency |
| Phase 2A tests | All 24 passed; REAL/unknown rejection, CLI privacy, budgets and scope included |
| Ruff lint / formatting | Passed; format tool reported 58 files already formatted |
| Strict mypy | Passed; no issues in 42 configured files |
| Secret scan | Passed; 70 tracked/nonignored project files, no findings |
| Locked dependencies | Passed; 45 packages checked with discovery extra |
| Actual terminal run | DEMO confirmed; 7 candidates, 28 H1 probes and bounded tick observations persisted locally |
| Git whitespace | Passed; only informational Windows line-ending notices |

JUnit evidence is in ignored test-results/phase2a.xml. Initial development typing/formatting findings were corrected before the full passing run. No remaining failed check is being waived. The isolated PostgreSQL test instance is stopped after verification; the owner's MT5 terminal is left open.

Source allowlist tests prohibit broker trading functions and TradeRequest in Phase 2A source, and enumerate every native SDK attribute used. The only MetaTrader5 import is discovery/sdk.py; deterministic domain files are unchanged. Existing Phase 1 scope assertions were updated solely for the explicitly authorized optional SDK and strengthened to prohibit order_check as well. No strategy/indicator/backtest/execution package, LIVE mode, entry-enabling config, position mutation or broker-write interface exists. The upstream binary includes trading APIs, but this application's wrapper neither exposes nor references them.

Native account extraction allowlists only company/server/currency/trade_mode. Tests verify REAL/unknown rejection before reads, DEMO acceptance, account-mode changes, exception suppression, private-field exclusion, unapproved ambiguity, Decimal normalization, quotes, UTC, empty/duplicate/invalid history, budgets and absence of continuity claims. Local artifact checks confirm no account/private keys and all five JSON files are Git-ignored. The scanner additionally rejects force-staged discovery files. No existing `.env` was read or modified.

## Files and commands

Created: discovery contracts, normalization, SDK boundary, provider, candidate search, bounded probe statistics and CLI under src/trading_ecosystem/discovery; tests/discovery; scripts/verify_phase2a.ps1; docs/PHASE2A_DISCOVERY_SPEC.md; this report. Changed: pyproject.toml/uv.lock for the optional Windows dependency and SDK typing boundary, .gitignore, scripts/secret_scan.py, tests/unit/test_scope.py, and README.md. The Phase 1 implementation and its frozen report/specification baseline remain unchanged otherwise.

Exact terminal-discovery commands executed from the repository root after installing the authorized extra:

```powershell
& "$env:USERPROFILE\.local\bin\uv.exe" add --optional discovery "MetaTrader5; sys_platform == 'win32'"
.\.venv\Scripts\python.exe -m trading_ecosystem.discovery --catalog-only
.\.venv\Scripts\python.exe -m trading_ecosystem.discovery
```

Locked repeat/verification commands:

```powershell
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
uv sync --locked --extra discovery
uv run --locked --extra discovery python -m trading_ecosystem.discovery
.\scripts\postgres_sandbox.ps1 -Action Start
$env:TE_TEST_DATABASE_URL = 'postgresql+psycopg://phase1_test@127.0.0.1:55439/postgres'
.\scripts\verify_phase2a.ps1
.\scripts\postgres_sandbox.ps1 -Action Stop
```

The combined verification script runs all Phase 1 and Phase 2A tests, including a fresh PostgreSQL migration, Ruff lint/format, strict mypy, secret scan and whitespace checks. Its tests use fakes for discovery and make no terminal calls. Actual terminal evidence is the separately executed bounded command. Official Windows dependency: MetaTrader5 5.0.6180 with NumPy 2.5.3; exact hashes and other versions are in [uv.lock](uv.lock).

Local outputs: provider_identity.json, symbol_candidates.json, instrument_metadata.json, bar_coverage.json and tick_coverage_probe.json in data/discovery; shared run IDs prevent mixing interrupted runs. See [PHASE2A_DISCOVERY_SPEC.md](docs/PHASE2A_DISCOVERY_SPEC.md) for contracts, privacy, interval/budget semantics and primary documentation. These observations do not approve mappings or authorize Phase 2B. STOP after Phase 2A.
