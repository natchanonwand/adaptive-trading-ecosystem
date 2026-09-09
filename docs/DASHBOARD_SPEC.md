# 8-bit monitoring dashboard specification

## Design and information hierarchy

Use pixel-art framing, sprite-like asset icons, and a restrained retro palette. Monetary values, timestamps, warnings, and tables use a highly readable text face. Animation never substitutes for status and respects reduced-motion preferences. Color is paired with text/icon labels.

Desktop layout: persistent environment/account strip; portfolio and risk summary; three asset panels; positions/orders; first-class Trading Calendar navigation; equity/drawdown; incidents and journal. Narrow screens stack these sections without hiding risk or environment status. All initial assets remain visible even when data or positions are absent.

| Area | Required content |
|---|---|
| Environment strip | RESEARCH/BACKTEST/PAPER/DEMO label, account alias, release, broker health, last reconciled UTC time, selected display timezone |
| Portfolio | Balance, equity, daily loss, drawdown, notional, used/reserved margin and stop-risk budgets |
| Asset cards | BTCUSD/XAUUSD/USTEC100, broker symbol, bid/ask, quote age, session status, position/fixed SL/fixed TP, actual-fill initial price risk, conceptual 1:2 RR and net R separately, SL/TP confirmation, latest signal and risk outcome |
| Strategy | Immutable release and parameters, warm-up progress, latest completed bar, optional diagnostic regime with unavailable state |
| Execution | Pending/unknown/partial requests, fill detail, protection confirmation, reconciliation incidents |
| Performance | Mode-specific equity/drawdown, costs, trades, report links and data-quality warnings |
| Trading Calendar | Daily closed-trade USD P/L, net R, closed trade count, win/loss state, timezone and completeness label; click-through day detail |
| Intelligence | Cited news/macro release time and available time, AI-summary label, uncertainty; explicit research-only status |
| Audit | Searchable events, reasons, UTC ordering, operator actions and evidence lineage |

## Trading Calendar

Provide a first-class month/day view, not merely a report link. Every day displays USD P/L, net R, number of closed trades, and WIN/LOSS/FLAT/NO_TRADES or INCOMPLETE state. Use [REPORT_SPEC.md](REPORT_SPEC.md)'s closed-episode attribution and summed net R exactly; label cell P/L as closed-trade P/L. A TP animation does not establish a winning trade: net costs determine win/loss.

Clicking a day opens daily portfolio summary, per-asset P/L, trades, execution incidents, and relevant market/research annotations when available. Include separately labeled interval account-equity P/L, unrealized P/L/cost reconciliation, fixed SL/TP details, exit reasons, ambiguity flags, and open exposure. UTC is the default calendar grouping and remains authoritative for risk/accounting. Optional Asia/Bangkok grouping is visibly labeled “Bangkok display day — not UTC risk day”; show the exact UTC interval and overlapping UTC risk days in detail. Switching grouping recalculates trade membership and totals, never resets risk. Timestamp display preference and calendar grouping are independent, explicitly labeled controls. Empty and unavailable annotations have explicit states.

## Decorative pixel-animation mapping

Text/icon status and server events are authoritative; animation is decorative only and cannot trigger a command, indicate a fill before confirmation, or change financial state. Honor `prefers-reduced-motion` with static equivalent sprites/icons; retain all text, timestamps, and incidents.

| State | Authoritative trigger | Decorative representation |
|---|---|---|
| IDLE | Healthy, no active work/exposure, or scheduled-closed market | Resting sprite |
| SCANNING | Healthy feed evaluating/warming completed bars while flat | Slow radar sweep |
| SIGNAL_FOUND | Deterministic entry intent emitted, not approval/fill | Brief signal spark |
| ORDER_PENDING | Durable submitted/unknown/partial entry or exit, or TP_PENDING | Waiting hourglass |
| POSITION_OPEN | Reconciled long exposure with confirmed SL/TP and no pending action | Steady guarded character |
| TAKE_PROFIT | Confirmed TP exit fill; retain quantity/episode status text | Brief target sparkle |
| STOP_LOSS | Confirmed SL exit fill; retain quantity/episode status text | Brief shield impact |
| ENTRY_PAUSED | Entry latch active, including drawdown halt (reason in text) | Closed gate |
| DAILY_HALT | Latched authoritative UTC daily-loss halt | Halt sign |
| STALE_DATA | Required open-session quote age >5s or account age >15s, or stale valuation | Faded/static signal |
| BROKER_DISCONNECTED | Broker connectivity explicitly lost | Broken-link sprite |

For overlapping conditions choose decoration by precedence: BROKER_DISCONNECTED > STALE_DATA > DAILY_HALT > ENTRY_PAUSED > STOP_LOSS/TAKE_PROFIT > ORDER_PENDING > POSITION_OPEN > SIGNAL_FOUND > SCANNING > IDLE. All concurrent text/icon flags stay visible; precedence cannot hide a halt or position. If both exit effects are eligible, show the newest confirmed event by account sequence. Exit/signal effects last at most three seconds from server receipt and are not replayed on reload; then derive current state again. Exceptional exits show their explicit reason in text and do not masquerade as TP/SL. Scheduled closure alone is not STALE_DATA. Backtests/paper use the same event meanings with conspicuous mode labels.

## Controls and state behavior

Default view is read-only. Authenticated operators can pause entries, request kill/flatten, and reset eligible halts through audited control endpoints. Flatten requires a confirmation displaying account alias and exposure. Pause takes effect immediately. A reset cannot override daily or drawdown eligibility, stale inputs, or missing approval. Release approval happens in a distinct evidence-review workflow with human authentication, never from an LLM annotation.

No buy/sell buttons, parameter sliders affecting runtime, live-mode toggle, or credential display exists. Pending commands show requested/acknowledged/reconciled states. A submitted flatten request must never display “flat” before confirmation.

Read models carry a common snapshot ID, ledger sequence, server time, and source ages. Do not combine independently fetched values into an apparently atomic portfolio summary. Refresh target is ≤5 seconds under the architecture test workload. Account data older than 15 seconds is STALE; quotes older than 5 seconds are ineligible for entry. Scheduled-closed markets show CLOSED with last-quote time; still distinguish broker disconnection. On network loss retain last known values with a conspicuous timestamp and unknown-current-state label.

Timestamp display defaults to `Asia/Bangkok`; provide UTC switch. Calendar grouping independently defaults to UTC as specified above. Grouping for risk days always uses UTC and labels the UTC reset boundary in the selected timezone. Exports retain UTC. Never use client clock alone to decide financial freshness or permission to execute.

## Measurable acceptance

- All three assets, environment, entry-enabled/paused state, and critical incidents are visible at desktop 1280×720 and mobile 390×844 via ordinary scrolling.
- Keyboard users can reach all controls with visible focus; text contrast ≥4.5:1 and large text/UI indicators ≥3:1 under the project's accessibility target.
- Status remains understandable in grayscale and with animation disabled.
- Snapshot fixtures produce exact displayed positions and cent-rounded totals matching reports.
- Simulated feed loss changes status within 15 seconds of last valid account data; quote entry eligibility ends after 5 seconds.
- UI refresh p95 ≤5 seconds for three assets, 100 open/pending audit items, and 10,000 journal rows using pagination on a declared local test host.
- Calendar fixtures spanning UTC/Bangkok midnight, multi-day episodes, partial exits, fees, no-trade days, and incomplete inputs match REPORT_SPEC exactly; drill-down preserves all required sections.
- All eleven animation states and precedence combinations match event fixtures; reduced-motion mode produces no animation and preserves authoritative text/icons.
- Fixed SL/TP and pending/failed target protection are visible; no channel-exit or short-entry controls exist for V0.
- Unauthorized commands fail at the server even if UI controls are forged.

Artwork, framework, identity provider, and deployment are unresolved design choices; they do not weaken operational visibility or permission boundaries.
