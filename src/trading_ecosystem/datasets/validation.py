"""Reject invalid records; quantify clock gaps without a calendar or repairs."""

from collections.abc import Sequence

from trading_ecosystem.datasets.contracts import (
    HOUR,
    Bar,
    Gap,
    Quality,
    QuarantinedObservation,
    Window,
)


def assess(
    bars: Sequence[Bar],
    window: Window,
    *,
    invalid: int = 0,
    invalid_ohlc: int = 0,
    failed: int = 0,
    issues: tuple[str, ...] = (),
    quarantine: tuple[QuarantinedObservation, ...] = (),
) -> Quality:
    problems = list(issues)
    seen: dict[object, Bar] = {}
    duplicates = conflicts = 0
    previous = None
    for bar in bars:
        if not window.requested_start <= bar.open_time < window.requested_end:
            problems.append("OUTSIDE_REQUESTED_BOUNDARIES")
        if previous is not None and bar.open_time < previous:
            problems.append("UNEXPECTED_ORDERING")
        previous = bar.open_time
        if bar.open_time in seen:
            duplicates += 1
            exclude = {"retrieved_at", "dataset_id"}
            if bar.model_dump(exclude=exclude) != seen[bar.open_time].model_dump(exclude=exclude):
                conflicts += 1
        seen[bar.open_time] = bar
    if duplicates:
        problems.append("DUPLICATE_TIMESTAMP")
    if conflicts:
        problems.append("CONFLICTING_DUPLICATE")
    # Sorting only a derived set for gap measurement never changes authoritative bars.
    times = sorted(
        {
            bar.open_time
            for bar in bars
            if window.requested_start <= bar.open_time < window.requested_end
        }
    )
    gaps = []
    cursor = window.requested_start
    prev = None
    for time in [*times, window.requested_end]:
        if time > cursor:
            gaps.append(
                Gap(
                    gap_start=cursor,
                    gap_end=time,
                    missing_clock_hours=int((time - cursor) / HOUR),
                    previous_bar=prev,
                    next_bar=time if time < window.requested_end else None,
                )
            )
        cursor = time + HOUR
        prev = time
    return Quality(
        validation_status="FAIL" if problems or invalid or failed else "PASS",
        bar_count=len(bars),
        duplicate_count=duplicates,
        conflicting_duplicate_count=conflicts,
        invalid_ohlc_count=invalid_ohlc,
        invalid_record_count=invalid,
        failed_chunk_count=failed,
        issues=tuple(sorted(set(problems))),
        gaps=tuple(gaps),
        missing_clock_hours=sum(gap.missing_clock_hours for gap in gaps),
        largest_gap=max((gap.missing_clock_hours for gap in gaps), default=0),
        outside_chunk_observation_count=len(quarantine),
        quarantined_observations=quarantine,
    )
