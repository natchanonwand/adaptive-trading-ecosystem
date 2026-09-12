"""One immutable episode from caller-supplied synthetic eligibility events."""

from datetime import timedelta

from trading_ecosystem.benchmarks.contracts import BenchmarkId
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.simulation.contracts import (
    CompletedEpisode,
    EventKind,
    ExitFill,
    ExitReason,
    ResultStatus,
    SimulationEvent,
    SimulationResult,
    SimulationSpec,
    StrategyExitIntent,
)
from trading_ecosystem.simulation.events import ordered_events
from trading_ecosystem.simulation.execution import open_position, protective_exit, strategy_exit
from trading_ecosystem.simulation.hashing import specification_sha256


def simulate(spec: SimulationSpec) -> SimulationResult:
    spec = SimulationSpec.model_validate(spec)
    identity = specification_sha256(spec)
    intent = spec.entry_intent
    signal_index = next(
        i for i, bar in enumerate(spec.bars) if bar.close_time == intent.decision_time
    )
    events = [
        SimulationEvent(
            sequence=0,
            kind=kind,
            time=intent.decision_time,
            bar_index=signal_index,
            detail=kind.name,
        )
        for kind in (EventKind.SIGNAL_DECISION, EventKind.ENTRY_INTENT)
    ]
    index = signal_index + 1
    if index == len(spec.bars):
        events.append(
            SimulationEvent(
                sequence=0,
                kind=EventKind.BOUNDARY_STATUS,
                time=intent.decision_time,
                bar_index=signal_index,
                detail=ResultStatus.NO_FILL_END_OF_DATA.value,
            )
        )
        return SimulationResult(
            specification_sha256=identity,
            status=ResultStatus.NO_FILL_END_OF_DATA,
            events=ordered_events(events),
            position=None,
            episode=None,
        )
    position = open_position(spec, spec.bars[index])
    if position is None:
        events.append(
            SimulationEvent(
                sequence=0,
                kind=EventKind.BOUNDARY_STATUS,
                time=spec.bars[index].open_time + timedelta(microseconds=1),
                bar_index=index,
                detail=ResultStatus.INVALID_INITIAL_PRICE_RISK.value,
            )
        )
        return SimulationResult(
            specification_sha256=identity,
            status=ResultStatus.INVALID_INITIAL_PRICE_RISK,
            events=ordered_events(events),
            position=None,
            episode=None,
        )
    for kind in (EventKind.ENTRY_FILL, EventKind.PROTECTIVE_STOP_ACTIVE):
        events.append(
            SimulationEvent(
                sequence=0,
                kind=kind,
                time=position.entry.modeled_execution_time,
                bar_index=index,
                detail=kind.name,
                entry=position.entry if kind == EventKind.ENTRY_FILL else None,
            )
        )
    if position.target is not None:
        events.append(
            SimulationEvent(
                sequence=0,
                kind=EventKind.TAKE_PROFIT_ACTIVE,
                time=position.entry.modeled_execution_time,
                bar_index=index,
                detail=EventKind.TAKE_PROFIT_ACTIVE.name,
            )
        )
    pending: StrategyExitIntent | None = None
    exit_fill: ExitFill | None = None
    exit_kind = EventKind.STOP_EXIT
    entry_index = index
    for index in range(entry_index, len(spec.bars)):
        bar = spec.bars[index]
        # A previously pending exit executes at open before any current high/low inspection.
        if pending is not None:
            reason = (
                ExitReason.TREND_EXIT
                if position.benchmark_id == BenchmarkId.B02
                else ExitReason.CHANNEL_EXIT
            )
            exit_fill = strategy_exit(pending, bar, spec.costs, reason)
            exit_kind = EventKind.STRATEGY_EXIT_FILL
            pending = None
            break
        exit_fill = protective_exit(position, bar, spec.costs)
        if exit_fill is not None:
            exit_kind = (
                EventKind.STOP_EXIT
                if exit_fill.reason == ExitReason.STOP_LOSS
                else EventKind.TARGET_EXIT
            )
            break
        pending = next(
            (item for item in spec.strategy_exits if item.decision_time == bar.close_time), None
        )
        if pending is not None:
            events.append(
                SimulationEvent(
                    sequence=0,
                    kind=EventKind.STRATEGY_EXIT_DECISION,
                    time=bar.close_time,
                    bar_index=index,
                    detail=pending.benchmark_id.value,
                )
            )
    if exit_fill is None and spec.flatten_at_boundary:
        bar = spec.bars[-1]
        exit_fill = ExitFill(
            reason=ExitReason.EVALUATION_BOUNDARY,
            price_reference_time=bar.close_time,
            modeled_execution_time=bar.close_time + timedelta(microseconds=1),
            price_source="BOUNDARY_CLOSE",
            exit_price=bar.close,
            spread_component=spec.costs.exit_spread_price,
            adverse_slippage_component=spec.costs.exit_slippage_price,
            gap_exit=False,
            intrabar_ambiguous=False,
        )
        exit_kind = EventKind.EVALUATION_BOUNDARY
        pending = None
    if exit_fill is not None:
        events.append(
            SimulationEvent(
                sequence=0,
                kind=exit_kind,
                time=exit_fill.modeled_execution_time,
                bar_index=index,
                detail=exit_fill.reason.value,
                exit=exit_fill,
            )
        )
        with arithmetic_context():
            episode = CompletedEpisode(
                position=position,
                exit=exit_fill,
                costs=spec.costs,
                gross_price_R=(exit_fill.exit_price - position.entry.entry_fill)
                / position.initial_price_risk,
            )
        return SimulationResult(
            specification_sha256=identity,
            status=ResultStatus.COMPLETED,
            events=ordered_events(events),
            position=None,
            episode=episode,
        )
    events.append(
        SimulationEvent(
            sequence=0,
            kind=EventKind.BOUNDARY_STATUS,
            time=spec.bars[-1].close_time,
            bar_index=len(spec.bars) - 1,
            detail=ResultStatus.OPEN_AT_EVALUATION_BOUNDARY.value,
        )
    )
    return SimulationResult(
        specification_sha256=identity,
        status=ResultStatus.OPEN_AT_EVALUATION_BOUNDARY,
        events=ordered_events(events),
        position=position,
        episode=None,
        pending_strategy_exit=pending,
    )
