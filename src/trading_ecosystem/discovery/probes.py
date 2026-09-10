"""Bounded discovery statistics only: no historical dataset ingestion."""

from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from trading_ecosystem.discovery.contracts import (
    BarCoverage,
    DiscoveryPlan,
    ProbeInterval,
    ReadOnlyMarketDataProvider,
    TickCoverage,
)


def bar_intervals(as_of: datetime) -> tuple[ProbeInterval, ...]:
    return tuple(
        ProbeInterval(
            label=f"last_{days}d", requested_start=as_of - timedelta(days=days), requested_end=as_of
        )
        for days in (7, 30, 90, 365)
    )


def tick_intervals(as_of: datetime) -> tuple[ProbeInterval, ...]:
    recent = [
        ProbeInterval(
            label=f"last_{days}d", requested_start=as_of - timedelta(days=days), requested_end=as_of
        )
        for days in (1, 7, 30)
    ]
    sampled = [
        ProbeInterval(
            label=f"sample_day_{days}d_ago",
            requested_start=as_of - timedelta(days=days),
            requested_end=as_of - timedelta(days=days - 1),
        )
        for days in (30, 90, 365)
    ]
    return tuple(recent + sampled)


def probe_bars(
    provider: ReadOnlyMarketDataProvider, symbol: str, interval: ProbeInterval
) -> BarCoverage:
    batch = provider.get_bars(symbol, interval.requested_start, interval.requested_end)
    times = [row.time for row in batch.rows]
    return BarCoverage(
        **interval.model_dump(),
        broker_symbol=symbol,
        retrieved_at=datetime.now(UTC),
        status="ERROR" if batch.error else "OBSERVED" if times else "EMPTY",
        actual_earliest=min(times, default=None),
        actual_latest=max(times, default=None),
        row_count=len(times),
        duplicate_count=len(times) - len(set(times)),
        invalid_OHLC_count=sum(not row.valid_ohlc for row in batch.rows),
        malformed_time_count=batch.malformed_time_count,
    )


def probe_ticks(
    provider: ReadOnlyMarketDataProvider, symbol: str, interval: ProbeInterval, budget: int
) -> TickCoverage:
    timestamps: Counter[datetime] = Counter()
    count = crossed = malformed = malformed_time = millis = queries = 0
    bid_present = ask_present = True
    cursor = interval.requested_start
    limited = budget <= 0
    error = False
    while cursor < interval.requested_end and count < budget and queries < 48:
        chunk_end = min(cursor + timedelta(hours=1), interval.requested_end)
        batch = provider.get_ticks(symbol, cursor, chunk_end)
        queries += 1
        if batch.error:
            error = True
            break
        malformed_time += batch.malformed_time_count
        remaining = budget - count
        rows = batch.rows[:remaining]
        for row in rows:
            count += 1
            timestamps[row.time] += 1
            good_bid = row.bid is not None and row.bid > 0
            good_ask = row.ask is not None and row.ask > 0
            bid_present = bid_present and good_bid
            ask_present = ask_present and good_ask
            malformed += not (good_bid and good_ask)
            if row.bid is not None and row.ask is not None and good_bid and good_ask:
                crossed += row.bid > row.ask
            millis += row.time_precision == "MILLISECOND"
        if batch.truncated or len(batch.rows) > remaining:
            limited = True
            # No inference about the unexamined remainder of this chunk.
            break
        cursor = chunk_end
        if count >= budget and cursor < interval.requested_end:
            limited = True
            break
    if queries >= 48 and cursor < interval.requested_end:
        limited = True
    return TickCoverage(
        **interval.model_dump(),
        broker_symbol=symbol,
        retrieved_at=datetime.now(UTC),
        status="ERROR"
        if error
        else "BUDGET_LIMIT"
        if limited
        else "OBSERVED"
        if count
        else "EMPTY",
        first_available_tick=min(timestamps, default=None),
        last_available_tick=max(timestamps, default=None),
        tick_count=count,
        bid_present=bid_present if count else None,
        ask_present=ask_present if count else None,
        crossed_quote_count=crossed,
        malformed_quote_count=malformed,
        malformed_time_count=malformed_time,
        duplicate_timestamp_count=count - len(timestamps),
        duplicate_timestamp_groups=sum(value > 1 for value in timestamps.values()),
        max_ticks_per_timestamp=max(timestamps.values(), default=0),
        millisecond_timestamp_count=millis,
        processed_until=cursor,
        requested_interval_fully_queried=cursor == interval.requested_end
        and not limited
        and not error,
        query_count=queries,
    )


def probe_symbol(
    provider: ReadOnlyMarketDataProvider, symbol: str, plan: DiscoveryPlan
) -> Iterator[BarCoverage | TickCoverage]:
    for interval in bar_intervals(plan.as_of):
        yield probe_bars(provider, symbol, interval)
    remaining = plan.max_ticks_total
    for interval in tick_intervals(plan.as_of):
        observed = probe_ticks(provider, symbol, interval, min(plan.max_ticks_per_probe, remaining))
        remaining -= observed.tick_count
        yield observed
