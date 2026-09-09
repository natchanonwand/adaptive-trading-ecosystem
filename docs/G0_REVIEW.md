# G0 owner-alignment review

Review date: 2026-09-09. Scope: documentation only.

**Result: ready for owner approval of G0.** Cross-document review found no remaining contradictions in the revised owner requirements. This is not owner approval, implementation authorization, or evidence that a strategy qualifies for execution.

## Changed documents

| Specification | Alignment changes |
|---|---|
| [PRODUCT_SPEC.md](PRODUCT_SPEC.md) | Fixed 2R owner scope, calendar, unchanged limits, intentional long-only scope |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Shared post-fill bracket calculation, immutable protection lineage, TP confirmation and paired-exit handling |
| [DATA_MODEL.md](DATA_MODEL.md) | TP fields in intents/decisions/requests/positions/trade reports, rounding, calendar contracts |
| [STRATEGY_V0.md](STRATEGY_V0.md) | Actual-fill 1:2 price RR, fixed SL/TP, partial-fill VWAP, exceptional exit reasons |
| [RISK_POLICY.md](RISK_POLICY.md) | Independent target validation/protection failures; existing risk limits preserved |
| [BACKTEST_SPEC.md](BACKTEST_SPEC.md) | Chronological quote SL/TP ordering, adverse-first ambiguous OHLC, target lineage |
| [REPORT_SPEC.md](REPORT_SPEC.md) | Price RR versus net R, exit attribution, calendar aggregation and day reconciliation |
| [DASHBOARD_SPEC.md](DASHBOARD_SPEC.md) | First-class Trading Calendar, day detail, eleven decorative states and reduced motion |
| [TEST_PLAN.md](TEST_PLAN.md) | Numeric target/R fixtures, partial fills, ordering, calendar, animation and scope acceptance |
| [ROADMAP.md](ROADMAP.md) | Updated milestones/checklist and separately qualified future short support |

## Resolved contradictions and explicit conventions

- Removed the former absence of a profit target and normal ten-bar exit. All three assets retain identical H1, long-only, EMA50/EMA200, 20-bar breakout, ATR14 × 2 fixed-stop rules. Only normal SL/TP exits remain; exceptional exits retain distinct labels.
- TP derives from actual entry/VWAP: entry + 2 × (entry − fixed stop), rounded upward to tick. Partial-entry targets are versioned during fill reconciliation and then frozen. No trailing or cost-compensating target adjustment exists.
- Net R uses actual filled initial price-risk USD, excluding cost reserves, as denominator; realized net costs affect the numerator. Cost-inclusive risk admission remains separate.
- Quotes decide SL/TP by chronology; unknown equal-time ordering blocks quote qualification. Unknown OHLC both-touch order assumes SL first and flags ambiguity. OHLC remains non-qualifying.
- Calendar cells use closed-episode P/L, summed net R, completed episode count, and net win/loss state. Interval equity P/L is separate. Bangkok grouping never changes authoritative UTC risk days.
- All eleven pixel states map to authoritative events with precedence, transient expiry, and static reduced-motion equivalents.
- Preserved 0.25% new-episode risk, 0.75% total open/reserved risk, 1.5% UTC daily-loss halt, and 5% drawdown halt. Bidirectional shorts require a later separately qualified candidate.

## Remaining decisions D01–D08

| ID | Remaining decision / owner | Dependency blocked |
|---|---|---|
| D01 | Operator: broker/server/demo account, symbols, valuation and SL/TP execution/amendment behavior, bounded post-fill TP workflow | Broker-specific qualification and connection |
| D02 | Research owner: licensed bid/ask history, quality, costs, calendars and contract metadata | Credible historical qualification |
| D03 | Strategy reviewer: formal acceptance of owner-defined hypothesis and prospective evidence plan | Candidate qualification; profitability remains unproven |
| D04 | Risk owner: formal versioned approval of preserved limits | Qualification/execution policy approval |
| D05 | Technical owner/operator: runtime, hosting, identity, secrets, retention, backup/restore and workload targets | Dependent implementation choices and demo deployment |
| D06 | Research/legal owner: news/macro providers, licenses, availability and retention | Intelligence integration |
| D07 | Reviewer/operator: qualified release, approved datasets/costs/mappings and execution approval | Trading readiness; no such evidence currently exists |
| D08 | Researcher/reviewer: registered holdout dates and forward observation window | Evaluation; depends on D02 |

## Verification

All local Markdown links in the eleven-document set were checked. Targeted searches reviewed profit-target absence, ten-bar/channel exits, RR definitions, TP lineage, and long-only/short references; remaining channel mentions explicitly prohibit that exit. Cross-contract review covered fill finalization, protection timing, tick arithmetic, simulation ordering, accounting/calendar attribution, risk limits, and approval sequencing. Documentation arithmetic examples were checked independently. Runtime tests remain not run; no runtime application code was created or changed. D01–D08 remain visible phase blockers and do not prevent owner review of this aligned specification baseline.
