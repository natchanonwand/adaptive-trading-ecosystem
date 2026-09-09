# Product specification

Status: specification baseline for review; no application implementation authorized.

## Purpose and scope

Build an auditable research, backtesting, and demo portfolio-monitoring system for canonical assets `BTCUSD`, `XAUUSD`, and `USTEC100`. These are internal identifiers, not promises that a broker exposes those exact symbols. Research results are evidence about simulated or demo behavior, not a promise of returns.

The product will provide historical research, deterministic backtesting, regime classification, news and macro intelligence, versioned strategies, independent portfolio risk controls, MetaTrader 5 demo execution, journaling, performance reports, and an 8-bit pixel-art monitoring dashboard. Controlled adaptation proposes candidates; it does not alter executing strategies.

## Binding invariants

1. LLM output is untrusted research content. An LLM has no broker credentials, execution endpoint access, approval authority, or ability to publish executable artifacts.
2. Strategies are deterministic functions of versioned inputs and prior state. Risk decisions are made independently and cannot be overridden by a strategy.
3. All broker access passes through an adapter. Broker writes are restricted to an authenticated execution service with independent account and approval checks.
4. Backtests and demo execution share the strategy and risk engines. Data feeds, clocks, and execution adapters differ.
5. Changes to strategy code, parameters, feature definitions, or instrument mappings invalidate the execution approval. Backtesting and forward testing are required before operational demo promotion.
6. Persisted timestamps are UTC; UI conversion to `Asia/Bangkok` is presentation-only.
7. Credentials never enter Git, reports, datasets, prompts, or logs. Live trading is disabled by default and unsupported by this baseline.
8. Every component has traceable tests and measurable acceptance criteria in [TEST_PLAN.md](TEST_PLAN.md).

## Users and workflows

- Researcher: import validated history, pin datasets, create candidates, run reproducible experiments, inspect costs and out-of-sample results.
- Operator: monitor demo health, approve eligible immutable releases, pause entries, request controlled flattening, inspect reconciliation incidents.
- Reviewer: inspect approval evidence, journal events, risk decisions, and reports without broker write access.
- LLM research assistant: summarize cited news and propose hypotheses in a separate research store for human review.

Workflow: dataset validation → candidate registration → deterministic backtest → frozen out-of-sample evaluation → paper forward test → approval → supervised operational demo → reporting. Optional isolated demo qualification follows paper qualification. No direct candidate-to-operational-demo path exists.

## V0 boundaries

V0 intentionally uses identical deterministic long-only rules for BTCUSD, XAUUSD, and USTEC100: H1 completed bid bars, EMA50/EMA200 trend filter, 20-bar breakout, ATR14 × 2 fixed stop, and a fixed 1:2 price risk/reward target calculated from actual entry fill/VWAP and rounded upward to a valid tick. Normal exits are fixed SL/TP; no trailing stop or normal channel exit is used. Safety, operator, protection-failure, and evaluation-boundary exits are separately labeled. One position per asset, a USD demo account, and no pyramiding apply. Bidirectional short support is a later candidate strategy requiring separate specification, backtesting, and forward qualification. The exact rules are in [STRATEGY_V0.md](STRATEGY_V0.md). News, macro events, and diagnostic regimes do not change V0 orders. The dashboard is observational except for authenticated operator controls. A first-class Trading Calendar shows daily USD P/L, net R, trade count, and win/loss state with drill-down. UTC accounting/risk days remain authoritative; optional Asia/Bangkok display-day grouping is explicitly distinct. Decorative pixel states and reduced-motion behavior are specified in [DASHBOARD_SPEC.md](DASHBOARD_SPEC.md). Live execution, options, short selling, leverage optimization, automatic parameter tuning, and autonomous promotion are outside V0.

Initial engineering choices are proposals: Python domain services and MT5 gateway, PostgreSQL event/operational storage, immutable Parquet research snapshots, and a TypeScript web UI. Final dependency versions and deployment topology require an architecture decision before implementation.

## Product acceptance

- All three canonical assets can be mapped to validated, effective-dated demo instruments; unknown mappings prevent execution.
- Identical pinned runs produce identical ordered decisions, fills, and ledger checksums.
- No strategy or LLM can bypass the risk gate; a real-account connection is refused before any order request.
- Every fill is traceable to an approved release, intent, risk decision, request, and reconciliation result.
- Every normal episode has traceable actual-fill initial price risk and fixed 2R TP; transaction costs affect net R without changing conceptual target RR.
- The 0.25% new-episode risk, 0.75% open/reserved risk, 1.5% UTC daily-loss halt, and 5% drawdown halt remain unchanged.
- Reports reconcile with the ledger; dashboard data matches the same snapshot and clearly indicates staleness.
- Promotion requires the evidence and gates in [TEST_PLAN.md](TEST_PLAN.md); missing evidence means rejection.

## Assumptions and unresolved decisions

| ID | Assumption or decision | Resolution and effect |
|---|---|---|
| D01 | USD-denominated MT5 demo account; broker and account not selected | Operator selects broker/server, validates demo flag, symbols, SL/TP trigger/fill semantics, amendment constraints, and five-second post-fill confirmation workflow; blocks broker-specific simulation and connection |
| D02 | Historical bid/ask, costs, calendars, and contract history not selected | Researcher documents licenses, quality, coverage, and metadata; blocks credible qualification |
| D03 | Owner-defined H1 long-only breakout with fixed 2R price target is a starting hypothesis | Reviewer approves V0 hypothesis; performance gates may reject it without relaxing controls |
| D04 | Risk limits are conservative engineering defaults, not personalized advice | Owner approves versioned limits before qualification; changes restart affected evidence |
| D05 | Single operator and dedicated account initially | Decide identity provider, secret store, deployment host, backup/restore policy before demo |
| D06 | No particular macro/news provider assumed | Decide licensing, availability timestamps, and retention before intelligence integration |
| D07 | No approved strategy, costs, dataset, or broker mapping currently exists | Specification consistency does not grant readiness to trade or implement |
| D08 | One frozen validation dataset and paper observation window per candidate | Reviewer registers windows before evaluation; exact dates depend on D02 |

## Document authority and consistency

This document owns scope and invariant requirements; [ARCHITECTURE.md](ARCHITECTURE.md) owns service boundaries; [DATA_MODEL.md](DATA_MODEL.md) owns contracts; [STRATEGY_V0.md](STRATEGY_V0.md) owns strategy rules; [RISK_POLICY.md](RISK_POLICY.md) owns limits and failure behavior; [BACKTEST_SPEC.md](BACKTEST_SPEC.md) owns simulation; [REPORT_SPEC.md](REPORT_SPEC.md) owns metrics; [DASHBOARD_SPEC.md](DASHBOARD_SPEC.md) owns presentation; [TEST_PLAN.md](TEST_PLAN.md) owns verification and promotion gates; [ROADMAP.md](ROADMAP.md) owns sequencing. A conflict blocks approval and must be resolved in all affected documents, never silently interpreted by implementation.
