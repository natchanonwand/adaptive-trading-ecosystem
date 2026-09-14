"""Deterministic source event merge and concurrency; no strategy recalculation."""

from datetime import timedelta
from typing import Any

from trading_ecosystem.portfolios.contracts import ASSET_ORDER, Episode, Interval


def common_interval(ranges: tuple[Interval, ...]) -> Interval:
    if len(ranges) != 3:
        raise ValueError("THREE_ASSET_INTERVALS_REQUIRED")
    return Interval(start=max(item.start for item in ranges), end=min(item.end for item in ranges))


def events(episodes: tuple[Episode, ...]) -> list[tuple[Any, ...]]:
    if len({item.episode_id for item in episodes}) != len(episodes):
        raise ValueError("DUPLICATE_EPISODE")
    merged = []
    for episode in episodes:
        merged.append(
            (
                episode.entry_time,
                ASSET_ORDER.index(episode.asset),
                episode.entry_priority,
                episode.entry_sequence,
                episode.episode_id,
                "ENTRY",
                episode,
            )
        )
        if episode.exit_time is not None:
            if episode.exit_priority is None or episode.exit_sequence is None:
                raise ValueError("MISSING_EXIT_ORDERING")
            merged.append(
                (
                    episode.exit_time,
                    ASSET_ORDER.index(episode.asset),
                    episode.exit_priority,
                    episode.exit_sequence,
                    episode.episode_id,
                    "EXIT",
                    episode,
                )
            )
    return sorted(merged, key=lambda event: event[:5])


def microseconds(delta: timedelta) -> int:
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def concurrency(episodes: tuple[Episode, ...], interval: Interval) -> dict[str, Any]:
    opened: dict[str, Episode] = {}
    counts = {str(index): 0 for index in range(4)}
    durations = {str(index): 0 for index in range(4)}
    previous = interval.start
    maximum = 0
    for time, _, _, _, _, kind, episode in events(episodes):
        clipped = min(time, interval.end)
        if clipped > previous:
            durations[str(len(opened))] += microseconds(clipped - previous)
            previous = clipped
        if kind == "ENTRY":
            if any(item.asset == episode.asset for item in opened.values()):
                raise ValueError("RESEARCH_INTEGRITY_SAME_ASSET_CONCURRENCY")
            opened[episode.episode_id] = episode
        else:
            if episode.episode_id not in opened:
                raise ValueError("RESEARCH_INTEGRITY_EXIT_WITHOUT_ENTRY")
            del opened[episode.episode_id]
        if len(opened) > 3:
            raise ValueError("RESEARCH_INTEGRITY_CONCURRENCY_ABOVE_THREE")
        maximum = max(maximum, len(opened))
        counts[str(len(opened))] += 1
    if previous < interval.end:
        durations[str(len(opened))] += microseconds(interval.end - previous)
    return {
        "max_concurrent_episodes": maximum,
        "max_same_asset_concurrency": 1 if episodes else 0,
        "max_concurrent_initial_risk_units": maximum,
        "post_event_count_distribution": counts,
        "time_microseconds_distribution": durations,
        "open_at_boundary": len(opened),
    }
