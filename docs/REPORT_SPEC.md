# Journal and report specification

## Report types and provenance

Generate backtest-run, forward-qualification, UTC daily demo, and release-comparison reports. Every report identifies mode, account alias, release and risk hashes, data/cost/calendar/simulator versions, reporting interval `[start,end)`, ledger sequence boundary, generation time, and completeness status. Never mix simulated, paper, and broker demo results into one return series.

Journal signal reasons, indicator inputs, risk checks/rejections, reservations, submission lifecycle, SL/TP protection status and target versions, fills, costs, broker reconciliation, health incidents, approvals, operator actions, and candidate lineage. Free-text operator notes and LLM summaries are labeled annotations; they cannot overwrite execution facts.

## Metric definitions

| Metric | Definition |
|---|---|
| Net P&L | Ending equity − starting equity − net external cash flows; includes realized/unrealized P&L and all costs |
| NAV/return | Unitized NAV starts at 1; issue/redeem units at immediately pre-flow NAV for deposits/withdrawals so flows do not change NAV; total return = ending NAV / starting NAV − 1 |
| Drawdown | `1 − NAV_t / max(NAV_s for s≤t)`; maximum over available valuation points; report sampling resolution |
| Daily return | Successive valid UTC midnight NAV ratio minus 1; missing boundary valuation means missing return, never zero |
| Annualized volatility | Sample standard deviation of valid daily returns × sqrt(365); mixed portfolio uses calendar days |
| Sharpe | Mean daily return / sample daily standard deviation × sqrt(365), assumed risk-free rate 0; fewer than 30 returns or zero deviation → N/A |
| CAGR | `(ending NAV / starting NAV)^(365.25/elapsed_days) − 1`; positive NAV and ≥365 days required, otherwise N/A |
| Trade count/win rate | Flat-to-flat episodes; winners have net P&L >0, zero P&L is not a win; wins / closed episodes |
| Profit factor | Sum positive episode net P&L / abs(sum negative episode net P&L); no losses → N/A with no-loss label |
| Expectancy | Mean net P&L per closed episode; also show net R = episode net P&L / initial_price_risk_usd (cost-exclusive denominator) |
| Exposure | Time with nonzero quantity / report duration, per asset; include closures in duration |
| Turnover | Sum absolute USD fill notional / mean valid sampled equity; disclose sample frequency |
| Costs | Commission, financing, and estimated slippage separately; spread attribution is informational and not deducted again |
| Operational quality | Rejection counts by reason, stale duration, unprotected duration, unknown requests, reconciliation differences, order-to-fill latency p50/p95 |

Price risk/reward is conceptually fixed at 1:2: `initial_price_risk = entry_fill_price - fixed_stop`, `take_profit_raw = entry_fill_price + 2 * initial_price_risk`, with upward tick rounding. Entry price is actual-fill VWAP for partial entries, finalized under [STRATEGY_V0.md](STRATEGY_V0.md). Record raw and rounded TP, target version history, rounding delta, and `effective_price_rr = (take_profit - entry_fill_price) / initial_price_risk`. This effective ratio may slightly exceed 2 due only to tick rounding.

`initial_price_risk_usd` is the validated instrument valuation of filled quantity loss from actual entry VWAP to fixed stop, excluding cost allowances. It is frozen with entry completion; exceptional exits before completion retain fill-level risk attribution and sum it once. `net_r = episode_net_pnl_usd / initial_price_risk_usd`. Do not use the cost-inclusive risk-admission budget as this denominator. Commissions, financing, and actual execution prices (including spread and slippage) affect the numerator without shifting conceptual TP. Never deduct embedded spread/slippage twice. A TP need not yield net +2R and an SL need not yield net −1R. Zero/invalid denominator gives N/A and a completeness warning; account-level unallocated charges remain separately visible.

Trade representations include actual entry VWAP, filled quantity, fixed SL, initial price risk and USD denominator, target_rr=2, raw/rounded TP, effective price RR, target history, costs, net P/L, net R, ambiguity flag, and exit reason/quantity breakdown. Normal reasons are TAKE_PROFIT and STOP_LOSS. RISK_SAFETY, OPERATOR_FLATTEN, PROTECTION_FAILURE, and EVALUATION_BOUNDARY are exceptional; show these separately and include them in total results. Multiple reasons produce MIXED with the underlying breakdown. Win/loss derives from net P/L, never solely from TP/SL reason.

## Trading Calendar aggregation

The first-class calendar defaults to authoritative UTC day grouping; timestamp display elsewhere may default to Asia/Bangkok. Each cell shows **closed-trade USD P/L**, **net R**, **closed trade count**, and WIN/LOSS/FLAT/NO_TRADES (or INCOMPLETE) state. Assign each flat-to-flat episode once to its final exit time's selected day, including its entire allocated costs. Sum episode net P/L and episode net R (not the ratio of summed profits to summed risk); trade count counts completed episodes, not fills. WIN/LOSS follows positive/negative summed episode net P/L; zero with trades is FLAT, no completed episodes is NO_TRADES with 0 P/L and 0R when inputs are complete. Any missing required episode value makes the affected total N/A/INCOMPLETE; never silently drop it.

Clicking a day shows daily portfolio summary, per-asset P/L (including zero-trade assets), completed trades and open/carrying exposure, execution incidents, and relevant market/research annotations when available. Show both the cell's closed-trade results and **account equity P/L for the interval** = end equity − start equity − net flows. These differ for multi-day trades, unrealized changes, cost timing, and unallocated fees; provide the reconciliation breakdown rather than treating calendar P/L as the daily risk numerator. Per-asset sections distinguish closed-episode attribution from interval realized/unrealized P/L and costs. Incidents are grouped by event time, annotations by available time, with cross-links from selected trades regardless of day.

Optional `Asia/Bangkok` grouping uses local midnight converted to a UTC `[start,end)` interval and is prominently labeled **Bangkok display day — not UTC risk day**. Recompute membership from original UTC timestamps; do not simply relabel UTC totals. Drill-down always shows overlapping UTC risk-day IDs, UTC boundary times, and their independent halt state. Current/incomplete days show provisional status. Historical correction changes the versioned projection, never past risk decisions. Calendar queries carry timezone, mode/account, snapshot/ledger boundary, and completeness status.

UTC daily loss controls use [RISK_POLICY.md](RISK_POLICY.md)'s explicit boundary formula; flow-adjusted NAV provides drawdown and return reporting. A flow without a valid pre-flow valuation marks NAV incomplete and pauses entries until resolved. Closed-session daily valuation carries the last valid mark only when the versioned calendar confirms closure, with a carried-mark label; unexpected missing prices cannot be carried silently.

## Views and artifacts

Include portfolio summary, equity/drawdown charts, per-asset results, Trading Calendar and day drill-down, trade list, costs, exposure, risk decisions, data quality, execution incidents, and qualification checklist. Compare candidates on the same data/cost assumptions, showing differences. Diagnostic regime performance is optional until its classifier is specified; render unavailable rather than inventing labels.

Outputs: versioned JSON for metrics/provenance, CSV for trades and ledger, and a self-contained HTML report. CSV exports neutralize formula-leading free text; timestamps remain UTC. Human display may offer Bangkok time alongside explicit timezone labels. P&L display rounds to cents while calculations preserve Decimal precision. Charts must label unknown/stale segments and simulated fills.

Acceptance: ledger identity holds within USD 0.01 after final display rounding; per-trade plus unallocated charges reconciles to account results with unrealized P&L shown separately; independent fixture calculations match every metric; all N/A reasons and incomplete inputs are visible. Historical/demo comparisons disclose modeling and monitoring-frequency differences.
