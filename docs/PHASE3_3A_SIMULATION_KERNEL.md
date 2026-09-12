# Phase 3.3A deterministic exploratory OHLC simulation kernel

Frozen baseline: `phase3.2-v0.1.0`. This package implements one LONG_ONLY synthetic episode from a preregistered benchmark definition, caller-supplied completed-bar eligibility intents, synthetic H1 bars, a price increment and explicit costs. It does not evaluate benchmark rules or load market datasets. No profitability comparison, equity curve or portfolio accounting is produced.

All input and output research records retain EXPLORATORY_RESEARCH_ONLY, qualification_eligible=false, MT5_CHART_BAR_BASIS_UNVERIFIED and MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH. These mechanics do not imply quote-replay fidelity or qualification evidence. No prior-phase timestamps, formulas, registry definitions or dataset evidence are changed.

## Inputs and immutable lifecycle

`simulate(SimulationSpec)` accepts one EntryIntent, one frozen benchmark, ordered nonoverlapping H1 SimulationBars, zero or more uniquely ordered StrategyExitIntents, a supplied positive PriceIncrement.tick_size, an explicit CostModel and an optional flatten_at_boundary flag. The entry must match an included completed signal bar close; strategy exits must match later included closes and the same benchmark. Eligibility availability equals its decision close. There are no lists of entry intents, position additions, short directions or sizing policies. Quantity is one fixed synthetic unit. Frozen contracts reject unknown fields, malformed bars, invalid costs and incompatible policies. Results contain immutable events and either an open position, one completed episode, or a no-fill status.

Eligibility is a caller attestation from Phase 3.2, not recomputed from supplied bars. The raw stop candidate is also a caller input, conventionally signal close minus twice Wilder ATR14. This layer neither calculates ATR nor verifies its provenance against an indicator history. Phase 3.3B may supply those inputs later; no historical orchestration exists here.

## Modeled time and entry

The next observed bar after the signal supplies ENTRY_PRICE_SOURCE=NEXT_OBSERVED_BAR_OPEN. The signal bar is never a fill source. No next bar returns NO_FILL_END_OF_DATA. Gaps are allowed without filling missing bars.

price_reference_time is the next bar open_time. modeled_execution_time is max(decision_time, price_reference_time) plus one microsecond. This preserves strict post-decision ordering even when next open equals the signal close, and avoids assigning execution before a later opening reference across a gap. The microsecond is only a deterministic convention, never observed latency. Phase 2B timestamps remain untouched.

For LONG, entry_fill = reference_open + entry_spread_price + entry_slippage_price. All three components remain separately recorded. No spread or broker assumption is inferred from bars. The initial protective stop rounds the supplied raw stop DOWN using the existing exact increment arithmetic; no tick is fetched externally. entry_fill must exceed fixed_stop or the result is INVALID_INITIAL_PRICE_RISK with no entry event or position. A positive raw stop smaller than one tick can floor to zero; no negative stop is supported.

Only B01 creates a target. initial_price_risk = entry_fill - fixed_stop; target_raw = entry_fill + 2 * initial_price_risk. Target rounding is UP to the supplied tick. This uses modeled actual entry, including its explicit spread/slippage components, not signal close. B02/B03/B04 have no fixed target. Stop and target never trail or otherwise change.

## Protective and strategy exits

The entry bar is exposed to its OHLC range after modeled opening entry. For every exposed bar without an already pending strategy exit:

1. If open <= stop, exit at open with STOP_LOSS and gap_exit=true.
2. Otherwise, for B01, if open >= target, exit at target with TAKE_PROFIT and gap_exit=true. No favorable improvement is awarded.
3. Otherwise inspect current low/high. Stop-only exits at stop; target-only exits at target. If both touch, assume STOP_LOSS first at stop and mark intrabar_ambiguous=true. Gap resolution does not receive an ambiguity flag.
4. Only if the position survives the bar may a supplied close-time strategy exit become pending. B02 uses TREND_EXIT; B03/B04 use CHANNEL_EXIT. B01 rejects strategy-exit intents.

A pending strategy exit executes at the next observed open with the same reference/execution timestamp convention as entry. It takes precedence over that next bar's protective checks, including gaps: the next intrabar range cannot replace an opening execution. A protective stop on the decision bar takes precedence over that bar's later close-time eligibility. Later eligibility cannot alter an already completed episode.

Gap exits use opening reference time plus one microsecond, no earlier than entry activation. Intrabar exits use the bar close as a deterministic recording time because the actual touch time is unknown; this is not an observed close fill. The price remains the triggered stop/target level. Event priority places intrabar protective resolution before any strategy decision at that same recording time.

## Boundary and costs

An exposed position without a normal exit returns OPEN_AT_EVALUATION_BOUNDARY, retaining any pending exit intent. No normal exit is invented. If and only if flatten_at_boundary=true, an exceptional EVALUATION_BOUNDARY exit uses the last observed close as its explicit reference price and close plus one microsecond as its ordering time. This exceptional boundary policy is separately labeled from next-open strategy execution. It does not fill a pending entry when no next bar exists.

CostModel requires explicit entry/exit spread and adverse slippage, commission_cash and financing_cash (zero must be supplied deliberately). Spreads, adverse slippage and commission are nonnegative; financing is signed to permit a supplied debit or credit. No real instrument monetary economics are assumed.

Entry price components are included in modeled entry as authorized. Exit price-path values preserve the specified open/stop/target prices; exit spread/slippage components are retained separately for future net accounting, not subtracted from the path price. Commission and financing remain separate cash assumptions. Costs never shift a target for compensation. gross_price_R = (exit_price - entry_fill) / initial_price_risk. No additional cost deduction is made in this gross ratio; entry components already embedded in entry_fill are not deducted a second time. Monetary net_R remains None, deferred until explicit monetary-risk conversion exists. No P&L or portfolio metric is computed.

## Ordering and identity

Events are canonically ordered by (modeled recording time, explicit numeric priority, observed bar index); duplicate keys are rejected. Sequence numbers are assigned only after this ordering. Priorities are:

| Priority | Event |
| --- | --- |
| 10 | SIGNAL_DECISION |
| 20 | ENTRY_INTENT |
| 30 | ENTRY_FILL |
| 40 | PROTECTIVE_STOP_ACTIVE |
| 50 | TAKE_PROFIT_ACTIVE |
| 60 | STOP_EXIT |
| 70 | TARGET_EXIT |
| 80 | STRATEGY_EXIT_DECISION |
| 90 | STRATEGY_EXIT_FILL |
| 100 | EVALUATION_BOUNDARY |
| 110 | BOUNDARY_STATUS |

Completed events contain no wall-clock IDs, random UUIDs or machine paths. SHA-256 specification identity includes schema/execution model versions, the frozen benchmark definition hash, bar fixture hash, tick contract, explicit costs, intents, boundary policy, classification and arithmetic version. Result identity includes the specification digest and complete output. Semantic Decimal serialization removes irrelevant scale and signed-zero differences; UTC times serialize with microsecond precision. Canonical JSON uses sorted keys, compact separators, UTF-8 and a final LF. Arithmetic uses the project's fresh Decimal34 half-even context, independent of caller context.

Changing future bars changes the full specification/result identity, as it should, but does not change earlier event contents or an already completed episode. Tests distinguish event-prefix causality from full-fixture identity.

## Verification

Run `scripts/verify_phase3_3a.ps1` with uv available and TE_TEST_DATABASE_URL pointing to the disposable loopback PostgreSQL test administrator. It runs locked dependency sync, every prior regression and the synthetic simulation suite, deterministic fixture/result checks, production AST scope checks, Ruff, formatting, strict mypy, secret scan, Phase 3.2 artifact verification and Git whitespace checks. Fresh database creation, migrations and cleanup use the existing integration fixture. Routine verification loads no real Phase 2B evidence and invokes no provider connection.

Stop after Phase 3.3A verification. Historical orchestration, real spread interpretation, benchmark comparisons and Phase 3.3B remain outside this implementation.
