"""Independent episodes, using frozen mechanics to bound each simulation call."""

from decimal import Decimal
from typing import Any

from trading_ecosystem.backtests.contracts import DatasetIdentity
from trading_ecosystem.backtests.metrics import split_at, splits, summarize
from trading_ecosystem.backtests.signals import signals
from trading_ecosystem.benchmarks.contracts import BenchmarkDefinition, ResearchDecision
from trading_ecosystem.benchmarks.hashing import (
    benchmark_definition_sha256,
    registry_sha256,
    verify_artifact,
)
from trading_ecosystem.datasets.contracts import Bar
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.research.indicators import wilder_atr
from trading_ecosystem.simulation import simulate
from trading_ecosystem.simulation.contracts import (
    CostModel,
    EntryIntent,
    PriceIncrement,
    SimulationBar,
    SimulationSpec,
    StrategyExitIntent,
)
from trading_ecosystem.simulation.execution import open_position, protective_exit
from trading_ecosystem.simulation.hashing import canonical_value, digest

COST_VERSION = "COST_MODEL_BASELINE_V0"
SIMULATION_VERSION = "exploratory-ohlc-v0.1.0"
COSTS = CostModel(
    entry_spread_price=Decimal(0),
    entry_slippage_price=Decimal(0),
    exit_spread_price=Decimal(0),
    exit_slippage_price=Decimal(0),
    commission_cash=Decimal(0),
    financing_cash=Decimal(0),
)


def research(
    identity: DatasetIdentity, bars: tuple[Bar, ...], definition: BenchmarkDefinition
) -> dict[str, Any]:
    verify_artifact()
    definition = BenchmarkDefinition.model_validate(definition)
    boundaries = splits(bars)
    decisions = signals(bars, definition)
    atr = wilder_atr(bars, definition.protective_stop.atr_period)
    simulation_bars = tuple(
        SimulationBar(
            **bar.model_dump(include={"open_time", "close_time", "open", "high", "low", "close"})
        )
        for bar in bars
    )
    definition_hash = benchmark_definition_sha256(definition)
    provenance = {
        **identity.model_dump(mode="json"),
        "benchmark_id": definition.benchmark_id.value,
        "benchmark_definition_hash": definition_hash,
        "simulation_model_version": SIMULATION_VERSION,
        "cost_model_version": COST_VERSION,
    }
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(bars):
        if decisions[index] != ResearchDecision.ENTRY_ELIGIBLE:
            index += 1
            continue
        signal = index
        value = atr[signal]
        if value is None:
            raise ValueError("ELIGIBLE_SIGNAL_WITHOUT_REQUIRED_ATR")
        with arithmetic_context():
            raw_stop = bars[signal].close - 2 * value
        record: dict[str, Any] = {
            **provenance,
            "signal_index": signal,
            "signal_time": bars[signal].close_time.isoformat(),
            "split": split_at(signal, boundaries).value,
            "entry_time": None,
            "entry_reference_open": None,
            "entry_fill": None,
            "fixed_stop": None,
            "take_profit": None,
            "exit_decision_time": None,
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "initial_price_risk": None,
            "gross_price_R": None,
            "holding_observed_bars": None,
            "holding_clock_hours": None,
            "intrabar_ambiguous": False,
            "gap_entry": False,
            "gap_exit": False,
            "cross_split": False,
            "preceded_by_gap_at_signal": signal > 0
            and bars[signal].open_time > bars[signal - 1].close_time,
        }
        if raw_stop <= 0:
            record["status"] = "INVALID_SIGNAL_STOP"
            records.append(record)
            index += 1
            continue
        intent = EntryIntent(
            benchmark_id=definition.benchmark_id,
            decision_time=bars[signal].close_time,
            available_at=bars[signal].available_at,
            signal_stop_raw=raw_stop,
        )
        end = min(signal + 1, len(bars) - 1)
        seed = SimulationSpec(
            benchmark=definition,
            bars=simulation_bars[signal : end + 1],
            entry_intent=intent,
            increment=PriceIncrement(tick_size=identity.tick_size),
            costs=COSTS,
        )
        exits: list[StrategyExitIntent] = []
        # Bound the call using frozen protective mechanics; the frozen lifecycle is authoritative.
        if signal + 1 < len(bars):
            position = open_position(seed, simulation_bars[signal + 1])
            if position is not None:
                for cursor in range(signal + 1, len(bars)):
                    end = cursor
                    if (
                        exits
                        or protective_exit(position, simulation_bars[cursor], COSTS) is not None
                    ):
                        break
                    if decisions[cursor] == ResearchDecision.EXIT_ELIGIBLE:
                        exits.append(
                            StrategyExitIntent(
                                benchmark_id=definition.benchmark_id,
                                decision_time=bars[cursor].close_time,
                                available_at=bars[cursor].available_at,
                            )
                        )
        spec = seed.model_copy(
            update={"bars": simulation_bars[signal : end + 1], "strategy_exits": tuple(exits)}
        )
        result = simulate(spec)
        record["status"] = result.status.value
        record["simulation_result"] = result.model_dump(mode="json")
        position = result.episode.position if result.episode else result.position
        if position is not None:
            record.update(
                entry_time=position.entry.modeled_execution_time.isoformat(),
                entry_reference_open=str(position.entry.reference_open),
                entry_fill=str(position.entry.entry_fill),
                fixed_stop=str(position.stop.fixed_stop),
                take_profit=str(position.target.target) if position.target else None,
                initial_price_risk=str(position.initial_price_risk),
                gap_entry=bars[signal + 1].open_time > bars[signal].close_time,
                cross_split=split_at(signal, boundaries) != split_at(end, boundaries),
                holding_observed_bars=end - signal,
            )
            terminal_time = (
                result.episode.exit.modeled_execution_time
                if result.episode
                else bars[end].close_time
            )
            elapsed = terminal_time - position.entry.modeled_execution_time
            with arithmetic_context():
                hours = (
                    Decimal(elapsed.days * 86400 + elapsed.seconds)
                    + Decimal(elapsed.microseconds) / 1000000
                ) / 3600
            record["holding_clock_hours"] = str(hours)
        if result.episode:
            exit = result.episode.exit
            record.update(
                exit_decision_time=exit.decision_time.isoformat() if exit.decision_time else None,
                exit_time=exit.modeled_execution_time.isoformat(),
                exit_price=str(exit.exit_price),
                exit_reason=exit.reason.value,
                gross_price_R=str(result.episode.gross_price_R),
                intrabar_ambiguous=exit.intrabar_ambiguous,
                gap_exit=exit.gap_exit,
            )
        records.append(record)
        # Require a later completed signal BAR, even for an opening exit.
        index = end + 1 if position is not None else signal + 1
    payload = {
        "research_schema_version": "phase3.3b-v0.1.0",
        **provenance,
        "registry_sha256": registry_sha256(),
        "spread_handling": "UNMODELED",
        "spread_reason": (
            "CURRENT_SNAPSHOT_ONLY metadata and no verified historical opening-spread availability"
        ),
        "tick_assumption": (
            "Frozen current snapshot trade_tick_size applied as exploratory increment"
        ),
        "costs": COSTS.model_dump(mode="json"),
        "split_policy": "ASSET_LOCAL_CHRONOLOGICAL_SPLIT",
        "splits": [item.model_dump(mode="json") for item in boundaries],
        "records": records,
        "metrics": summarize(records, decisions.count(ResearchDecision.ENTRY_ELIGIBLE)),
        "split_metrics": {
            item.name.value: summarize(
                [record for record in records if record["split"] == item.name.value],
                decisions[item.first_index : item.end_index_exclusive].count(
                    ResearchDecision.ENTRY_ELIGIBLE
                ),
            )
            for item in boundaries
        },
    }
    canonical = canonical_value(payload)
    if not isinstance(canonical, dict):
        raise TypeError("INVALID_RESEARCH_RESULT")
    return {**canonical, "result_sha256": digest(canonical)}
