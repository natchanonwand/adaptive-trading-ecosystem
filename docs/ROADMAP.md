# Roadmap

All phases below are planned, not implemented. The present deliverable ends at specifications; user authorization is required before Phase 1.

| Phase | Deliverables | Dependencies and exit criteria |
|---|---|---|
| 0 — Specification review | Ten aligned specifications, [G0_REVIEW.md](G0_REVIEW.md), assumptions and decision register | G0 review; resolve any contradictions; obtain implementation authorization |
| 1 — Contracts and safe foundations | Domain contracts, UTC/arithmetic utilities, immutable config, event journal, test harness, secret scanning, entry-disabled modes | Choose runtime/storage/deployment baseline D05; component fixtures pass; no broker writes |
| 2 — Historical data | Canonical asset mapping, metadata/calendar validation, licensed snapshots and quality reports | D01/D02 resolved for research; all three assets have traceable history and cost/valuation fixtures |
| 3 — Deterministic research | Shared indicators/strategy/risk engines, quote simulator, exploratory OHLC simulator, reports | G1; reproducible checksums, accounting, actual-fill 2R bracket, partial-fill, and quote/OHLC ordering tests pass |
| 4 — Historical qualification | Frozen candidate, registered holdout, baseline and stress evidence | G2; failed hypotheses remain rejected and require a new evidence plan |
| 5 — Forward observation | Paper feed/adapter, reconciliation projections, basic operational views | G3; extend observation if sample minima not met |
| 6 — MT5 demo | Isolated gateway, verified demo identity, broker-specific fixtures, operator controls and runbooks | G4; supervised protected entry/exit smoke test; no live support |
| 7 — Pixel dashboard and reporting | Full 8-bit presentation with eleven decorative states/reduced motion, first-class Trading Calendar and UTC/Bangkok drill-down, accessibility, journal search, daily and comparison reports | Dashboard/report matrix passes; uses the operational read models already established |
| 8 — Intelligence and regimes | Licensed news/macro ingestion, vintage-aware research, cited LLM summaries, deterministic diagnostic classifier | D06 and classifier design resolved; leakage/security tests pass; V0 remains unaffected |
| 9 — Controlled adaptation | Proposal registry, reviewed experiments, immutable evidence lineage, qualified rollback | G5 and G1–G4 for every behavior-changing candidate; no automatic promotion |

Basic health, risk visibility, journaling, reporting, and operator controls are prerequisites to demo; Phase 7 adds the complete visual treatment, not the first safety view. Regime detection starts as diagnostics; using it in signals is a new strategy requiring its own specification and qualification.

## Decisions to close

- Owner/operator: D01 broker, dedicated demo account, supported symbol contracts and gateway behavior.
- Research owner: D02 licensed history, quote availability, costs and calendars; D08 fixed evaluation windows.
- Strategy reviewer: D03 hypothesis and prospective evidence plan; risk owner: D04 policy values.
- Technical owner/operator: D05 runtime/dependencies, deployment, identity/secrets, retention, backup/restore targets, workload benchmark.
- Research/legal owner: D06 provider usage rights and provenance. Until an owner is assigned, that decision remains open.
- D07 is closed only by completed evidence and explicit approvals; creating these documents does not close it.

Do not assign calendar completion dates until data/broker dependencies and team capacity are known. Forward qualification has unavoidable elapsed-time and sample requirements; coding speed cannot replace them.

## Specification consistency checklist

- [x] Three canonical assets are separate from effective-dated broker symbols.
- [x] V0 is identically H1 bid-bar, long-only, EMA50/EMA200, 20-bar breakout, ATR14 × 2 fixed stop, actual-fill fixed 1:2 price RR target, deterministic, with UTC bar boundaries; no trailing or channel exit.
- [x] Strategy emits intents; independent risk determines quantity; adapter alone handles broker protocol.
- [x] Five-minute entry expiry, five-second quote/risk approval freshness, and fifteen-second account freshness agree across documents.
- [x] TP lineage, partial-fill finalization, rounding, price RR/net R distinction, and exceptional exit reasons agree.
- [x] Quote chronology determines TP/SL; unknown OHLC both-touch sequence is stop-first and flagged ambiguous.
- [x] Trading Calendar closed-trade metrics and UTC/Bangkok day grouping are distinct from UTC equity-loss controls; all eleven decorative states preserve authoritative text.
- [x] Reports and controls use the same equity ledger and flow-aware drawdown definitions.
- [x] Backtest price/cost models and qualification fidelity are explicit; OHLC approximation cannot qualify.
- [x] Backtest precedes paper forward testing, which precedes any demo qualification or operational promotion.
- [x] Candidate changes invalidate approvals; LLM research has no execution authority.
- [x] Every component maps to measurable tests; outstanding provider/deployment choices block dependent phases.
- [x] Live trading is unsupported and credentials are excluded from Git and research content.

This checklist records design alignment, not executed software tests or human approval. Remaining choices are documented in [PRODUCT_SPEC.md](PRODUCT_SPEC.md); the next action is specification review and decision resolution, not application implementation.

Bidirectional short support is deliberately deferred to a later candidate with its own specification and G1–G4 qualification. It cannot be enabled within V0 by configuration. Owner-alignment findings and remaining D01–D08 decisions are in [G0_REVIEW.md](G0_REVIEW.md).
