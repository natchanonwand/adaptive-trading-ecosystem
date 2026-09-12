"""Explicit price-path mechanics; monetary costs remain separate."""

from datetime import datetime, timedelta

from trading_ecosystem.benchmarks.contracts import TakeProfitKind
from trading_ecosystem.domain.arithmetic import (
    arithmetic_context,
    price_tick_ceiling,
    price_tick_floor,
)
from trading_ecosystem.simulation.contracts import (
    CostModel,
    ExitFill,
    ExitReason,
    ModeledEntryFill,
    ProtectiveStop,
    SimulatedPosition,
    SimulationBar,
    SimulationSpec,
    StrategyExitIntent,
    TakeProfitTarget,
)


def opening_time(decision: datetime, reference: datetime) -> datetime:
    return max(decision, reference) + timedelta(microseconds=1)


def open_position(spec: SimulationSpec, bar: SimulationBar) -> SimulatedPosition | None:
    with arithmetic_context():
        intent, costs = spec.entry_intent, spec.costs
        price = bar.open + costs.entry_spread_price + costs.entry_slippage_price
        stop = price_tick_floor(intent.signal_stop_raw, spec.increment.tick_size)
        if price <= stop:
            return None
        entry = ModeledEntryFill(
            decision_time=intent.decision_time,
            price_reference_time=bar.open_time,
            modeled_execution_time=opening_time(intent.decision_time, bar.open_time),
            reference_open=bar.open,
            spread_component=costs.entry_spread_price,
            adverse_slippage_component=costs.entry_slippage_price,
            entry_fill=price,
        )
        risk = price - stop
        target = None
        if spec.benchmark.take_profit.kind == TakeProfitKind.FIXED_PRICE_R_MULTIPLE:
            raw = price + 2 * risk
            target = TakeProfitTarget(
                target_raw=raw,
                target=price_tick_ceiling(raw, spec.increment.tick_size),
            )
        return SimulatedPosition(
            benchmark_id=spec.benchmark.benchmark_id,
            entry=entry,
            stop=ProtectiveStop(signal_stop_raw=intent.signal_stop_raw, fixed_stop=stop),
            target=target,
            initial_price_risk=risk,
        )


def protective_exit(
    position: SimulatedPosition,
    bar: SimulationBar,
    costs: CostModel,
) -> ExitFill | None:
    stop, target = position.stop.fixed_stop, position.target
    gap, ambiguous = False, False
    if bar.open <= stop:
        price, reason, gap = bar.open, ExitReason.STOP_LOSS, True
    elif target is not None and bar.open >= target.target:
        price, reason, gap = target.target, ExitReason.TAKE_PROFIT, True
    elif bar.low <= stop:
        price, reason = stop, ExitReason.STOP_LOSS
        ambiguous = target is not None and bar.high >= target.target
    elif target is not None and bar.high >= target.target:
        price, reason = target.target, ExitReason.TAKE_PROFIT
    else:
        return None
    return ExitFill(
        reason=reason,
        price_reference_time=bar.open_time if gap else bar.close_time,
        modeled_execution_time=(
            max(position.entry.modeled_execution_time, bar.open_time + timedelta(microseconds=1))
            if gap
            else bar.close_time
        ),
        price_source="BAR_OPEN" if gap else "INTRABAR_LEVEL",
        exit_price=price,
        spread_component=costs.exit_spread_price,
        adverse_slippage_component=costs.exit_slippage_price,
        gap_exit=gap,
        intrabar_ambiguous=ambiguous,
    )


def strategy_exit(
    intent: StrategyExitIntent,
    bar: SimulationBar,
    costs: CostModel,
    reason: ExitReason,
) -> ExitFill:
    return ExitFill(
        reason=reason,
        decision_time=intent.decision_time,
        price_reference_time=bar.open_time,
        modeled_execution_time=opening_time(intent.decision_time, bar.open_time),
        price_source="NEXT_OBSERVED_BAR_OPEN",
        exit_price=bar.open,
        spread_component=costs.exit_spread_price,
        adverse_slippage_component=costs.exit_slippage_price,
        gap_exit=False,
        intrabar_ambiguous=False,
    )
