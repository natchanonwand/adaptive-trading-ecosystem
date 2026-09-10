"""Versioned Decimal context and explicit instrument-boundary rounding."""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Literal

from trading_ecosystem.domain.primitives import positive_decimal

ARITHMETIC_VERSION = "decimal34-half-even-v1"
PRECISION = 34


@contextmanager
def arithmetic_context() -> Iterator[Context]:
    # A fresh context also prevents caller flags/traps/precision changing results.
    with localcontext(Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)) as context:
        yield context


def _step(
    value: object, step: object, direction: Literal["floor", "ceiling", "nearest"]
) -> Decimal:
    price = positive_decimal(value)
    increment = positive_decimal(step)
    # Integer ratios prevent division rounding across a tick at precision 34.
    pn, pd = price.as_integer_ratio()
    sn, sd = increment.as_integer_ratio()
    numerator, denominator = pn * sd, pd * sn
    units, remainder = divmod(numerator, denominator)
    if direction == "ceiling" and remainder:
        units += 1
    if direction == "nearest":
        twice = remainder * 2
        if twice > denominator or (twice == denominator and units % 2):
            units += 1
    # Construct the exact multiple, then validate representability instead of
    # silently rounding a boundary to a non-permitted tick.
    sign, digits, exponent = increment.as_tuple()
    coefficient = int("".join(map(str, digits))) * units
    result = Decimal((sign, tuple(map(int, str(coefficient))), int(exponent)))
    if result == 0:
        return Decimal(0)
    return positive_decimal(result)


def price_tick_floor(value: object, tick: object) -> Decimal:
    return _step(value, tick, "floor")


def price_tick_ceiling(value: object, tick: object) -> Decimal:
    return _step(value, tick, "ceiling")


def nearest_permitted_tick(value: object, tick: object) -> Decimal:
    """Explicit opt-in only; exact ties use half-even on the tick index."""
    return _step(value, tick, "nearest")


def lot_step_floor(value: object, step: object) -> Decimal:
    return _step(value, step, "floor")
