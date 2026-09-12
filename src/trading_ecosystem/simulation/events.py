"""Canonical event ordering, independent of incidental container ordering."""

from trading_ecosystem.simulation.contracts import SimulationEvent


def ordered_events(events: list[SimulationEvent]) -> tuple[SimulationEvent, ...]:
    ordered = sorted(events, key=lambda event: (event.time, int(event.kind), event.bar_index))
    keys = [(event.time, event.kind, event.bar_index) for event in ordered]
    if len(set(keys)) != len(keys):
        raise ValueError("DUPLICATE_EVENT_ORDER_KEY")
    return tuple(
        event.model_copy(update={"sequence": index}) for index, event in enumerate(ordered)
    )
