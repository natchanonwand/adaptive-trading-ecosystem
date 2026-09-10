from decimal import Decimal, localcontext

from hypothesis import given
from hypothesis import strategies as st

from tests.conftest import draft
from trading_ecosystem.domain.arithmetic import lot_step_floor, price_tick_ceiling, price_tick_floor
from trading_ecosystem.domain.canonical import CanonicalPayload
from trading_ecosystem.domain.events import GENESIS_HASH, seal_event
from trading_ecosystem.journal.contracts import verify_chain


@given(st.integers(1, 10**12), st.integers(1, 10**6))
def test_rounding_is_exact_multiple_and_bounds(value: int, step: int) -> None:
    price, tick = Decimal(value).scaleb(-4), Decimal(step).scaleb(-4)
    low, high = price_tick_floor(price, tick), price_tick_ceiling(price, tick)
    assert low <= price <= high
    assert high - low <= tick
    assert low % tick == 0 and high % tick == 0
    assert lot_step_floor(price, tick) == low
    with localcontext() as context:
        context.prec = 3
        assert price_tick_floor(price, tick) == low


@given(st.dictionaries(st.text(max_size=12), st.integers(), max_size=20))
def test_map_order_does_not_change_hash(values: dict[str, int]) -> None:
    assert (
        CanonicalPayload.from_mapping(values).payload_hash
        == CanonicalPayload.from_mapping(dict(reversed(list(values.items())))).payload_hash
    )


@given(st.integers(1, 30))
def test_chain_lengths_and_hashes(count: int) -> None:
    initial = draft()
    previous = GENESIS_HASH
    events = []
    for sequence in range(1, count + 1):
        event = seal_event(draft(initial.account_id), sequence, previous)
        assert event == seal_event(event.draft(), sequence, previous)
        events.append(event)
        previous = event.event_hash
    assert verify_chain(events, initial.account_id) == previous
