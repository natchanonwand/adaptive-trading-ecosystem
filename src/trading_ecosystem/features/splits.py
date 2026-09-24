"""Chronological locked splits; crossing groups are purged, never fragmented."""

from datetime import datetime
from typing import Literal

from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.mt5.client import Record


def split(
    rows: list[Record],
    outcomes: list[Record],
    train_end: datetime,
    validation_end: datetime,
    *,
    group_by: Literal["episode", "session"] = "episode",
) -> Record:
    if train_end.tzinfo is None or validation_end.tzinfo is None or train_end >= validation_end:
        raise ValueError("INVALID_SPLIT_BOUNDARIES")
    if group_by not in ("episode", "session"):
        raise ValueError("INVALID_SPLIT_GROUP")
    outcome_map = {r["episode_id"]: r for r in outcomes}
    groups: dict[str, list[Record]] = {}
    for row in rows:
        # Also co-group every candidate/symbol causal sequence within its session.
        key = row["session_id"] if group_by == "session" else row["sequence_group_id"]
        groups.setdefault(key, []).append(row)
    assignments: Record = {}
    for members in groups.values():
        start = min(utc_timestamp(r["prediction_cutoff"]) for r in members)
        end = max(
            max(
                utc_timestamp(r["prediction_cutoff"]),
                utc_timestamp(outcome_map[r["episode_id"]]["available_at"]),
            )
            for r in members
        )

        def bucket(at: datetime) -> str:
            return (
                "train" if at < train_end else "validation" if at < validation_end else "locked_oos"
            )

        label = bucket(start) if bucket(start) == bucket(end) else "purged_boundary_crossing"
        for row in members:
            assignments[row["row_id"]] = label
    return dict(
        group_by=group_by,
        train_end=train_end.isoformat(),
        validation_end=validation_end.isoformat(),
        locked_oos=True,
        assignments=dict(sorted(assignments.items())),
    )
