"""Validated immutable H1 observations and clock-gap metadata."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_ecosystem.datasets.contracts import HOUR, Bar
from trading_ecosystem.domain.arithmetic import arithmetic_context


def validated_bars(bars: Sequence[Bar]) -> tuple[Bar, ...]:
    result = tuple(bars)
    previous: Bar | None = None
    for bar in result:
        if not isinstance(bar, Bar):
            raise ValueError("NORMALIZED_H1_BAR_REQUIRED")
        # Revalidate even a contract assembled with model_construct/model_copy.
        with arithmetic_context():
            Bar.model_validate(bar.model_dump())
        if previous is not None:
            if bar.open_time <= previous.open_time:
                raise ValueError("STRICT_CHRONOLOGY_REQUIRED")
            if (
                bar.dataset_id != previous.dataset_id
                or bar.canonical_asset != previous.canonical_asset
                or bar.broker_symbol != previous.broker_symbol
                or bar.instrument_metadata_reference != previous.instrument_metadata_reference
            ):
                raise ValueError("MIXED_OBSERVATION_SERIES")
        previous = bar
    return result


def observed_closes(bars: Sequence[Bar]) -> tuple[Decimal, ...]:
    """Extract authoritative closes without conversion or artifact access."""
    return tuple(bar.close for bar in validated_bars(bars))


@dataclass(frozen=True)
class GapMetadata:
    open_time: datetime
    preceded_by_gap: bool
    elapsed_clock_hours: int | None
    gap_duration_hours: int
    missing_clock_hours: int


def gap_metadata(bars: Sequence[Bar]) -> tuple[GapMetadata, ...]:
    """Gap duration is open-to-open separation when >1 hour, otherwise zero."""
    observations = validated_bars(bars)
    result = []
    previous: Bar | None = None
    for bar in observations:
        elapsed = (bar.open_time - previous.open_time) // HOUR if previous else None
        gap = elapsed is not None and elapsed > 1
        result.append(
            GapMetadata(
                open_time=bar.open_time,
                preceded_by_gap=gap,
                elapsed_clock_hours=elapsed,
                gap_duration_hours=elapsed if gap and elapsed is not None else 0,
                missing_clock_hours=max(elapsed - 1, 0) if elapsed is not None else 0,
            )
        )
        previous = bar
    return tuple(result)
