"""Foreground bounded controller around the unchanged Phase 4B Observer."""

import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, select, text

from trading_ecosystem.campaigns.contracts import RealEaQualificationCampaign
from trading_ecosystem.campaigns.health import account_guard, inspect_health
from trading_ecosystem.campaigns.journal import Journal, create
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.contracts import ObservationSession
from trading_ecosystem.observer.native import NativeObserverClient
from trading_ecosystem.observer.runtime import Observer, ObserverClient
from trading_ecosystem.observer.store import episodes


def completed(observer: Observer, candidate_id: str) -> int:
    with observer.engine.connect() as conn:
        rows = conn.execute(
            select(episodes.c.body).where(episodes.c.session_id == observer.session.session_id)
        ).scalars()
        return sum(
            r["closed_at"] is not None
            and r["ea_metrics_eligible"]
            and r["attribution"]["candidate_id"] == candidate_id
            for r in rows
        )


def db_size(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT pg_database_size(current_database())")).scalar_one())


def run(
    spec: RealEaQualificationCampaign,
    client: ObserverClient,
    engine: Engine,
    root: Path,
    *,
    restart_after_seconds: int | None = None,
) -> Record:
    now = datetime.now(UTC)
    if (
        restart_after_seconds is not None
        and not 1 <= restart_after_seconds < (spec.window_end - now).total_seconds()
    ):
        raise ValueError("RESTART_MUST_BE_INSIDE_BOUNDED_WINDOW")
    gate = inspect_health(spec, client, engine, now)
    if not gate["passed"]:
        raise ValueError(
            "CAMPAIGN_START_GATE_FAILED: " + ",".join(k for k, v in gate["checks"].items() if not v)
        )
    native = isinstance(client, NativeObserverClient)
    if not native:
        raise ValueError("REAL_CAMPAIGN_REQUIRES_NATIVE_READ_CLIENT")
    create(root, spec)
    journal = Journal(root)
    session = ObservationSession(
        session_id=spec.campaign_id,
        account_scope=spec.account_scope,
        broker=spec.broker,
        server_scope=spec.server,
        margin_mode=client.account_info()["margin_mode"],
        started_at=now,
        terminal_build=spec.terminal_build,
        config=spec.observer_config,
    )
    origin = "NATIVE_DEMO_READ_ONLY"
    journal.record(
        "START",
        dict(
            at=now.isoformat(),
            origin=origin,
            gate=gate,
            session=session.model_dump(mode="json"),
            db_size_bytes=db_size(engine),
        ),
    )
    observer = Observer(client, engine, session)
    tracing_owned = not tracemalloc.is_tracing()
    if tracing_owned:
        tracemalloc.start()
    began, cpu, deadline = (
        time.monotonic(),
        time.process_time(),
        (spec.window_end - now).total_seconds(),
    )
    status, reason, restarted, polls, misses = "RUNNING", None, False, 0, 0
    last_tick: float | None = None
    last_health = began
    latencies: list[float] = []
    try:
        while time.monotonic() - began < deadline and datetime.now(UTC) < spec.window_end:
            tick, at = time.monotonic(), datetime.now(UTC)
            gap = None if last_tick is None else tick - last_tick
            if gap is not None and gap > spec.maximum_gap_seconds:
                status, reason = "DEGRADED", "POLLING_GAP_LIMIT"
                journal.record("GAP", dict(at=at.isoformat(), seconds=gap))
                break
            account_guard(spec, client)
            if tick - last_health >= 5:
                health = inspect_health(spec, client, engine, at)
                journal.record("HEALTH", health)
                last_health = tick
                if not health["passed"]:
                    status, reason = "PAUSED", "CONTINUITY_HEALTH_FAILED"
                    break
            if (
                restart_after_seconds is not None
                and not restarted
                and tick - began >= restart_after_seconds
            ):
                observer = Observer(client, engine, session)
                restarted = True
                journal.record("RESTART", dict(at=at.isoformat(), recovered=observer.recovered))
            success = observer.step(at)
            # Detect switches during a poll as well as before it; never qualify uncertain rows.
            account_guard(spec, client)
            elapsed = time.monotonic() - tick
            latencies.append(elapsed)
            polls += 1
            misses += elapsed > spec.observer_config.poll_ms / 1000
            journal.record(
                "POLL",
                dict(
                    at=at.isoformat(),
                    success=success,
                    elapsed_seconds=elapsed,
                    gap_seconds=gap,
                    connected=True,
                ),
            )
            if not success:
                status, reason = "PAUSED", "OBSERVER_FAILED_NO_QUALIFICATION"
                break
            if elapsed > spec.maximum_gap_seconds:
                status, reason = "DEGRADED", "POLL_LATENCY_LIMIT"
                journal.record("GAP", dict(at=at.isoformat(), seconds=elapsed))
                break
            if (
                spec.episode_target
                and completed(observer, spec.metadata.candidate.ea_id) >= spec.episode_target
            ):
                break
            last_tick = tick
            time.sleep(
                min(
                    max(0, spec.observer_config.poll_ms / 1000 - (time.monotonic() - tick)),
                    max(0, deadline - (time.monotonic() - began)),
                )
            )
        if status == "RUNNING":
            account_guard(spec, client)
            observer.last_history = None
            if not observer.step(datetime.now(UTC)):
                status, reason = "PAUSED", "FINAL_HISTORY_RECONCILIATION_FAILED"
            else:
                account_guard(spec, client)
                status = "STOPPED_RECONCILED"
    except KeyboardInterrupt:
        status, reason = "PAUSED", "USER_INTERRUPTION_REQUIRES_RECONCILIATION"
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else "OBSERVATION_OR_DATABASE_FAILURE"
        status = "INVALIDATED" if message.startswith("INVALIDATED") else "PAUSED"
        reason = message
    ended = datetime.now(UTC)
    try:
        observer.stop(ended)
    except Exception:
        status, reason = "PAUSED", "STOP_DATABASE_UNAVAILABLE"
    ordered = sorted(latencies)
    result = dict(
        status=status,
        reason=reason,
        started_at=now.isoformat(),
        ended_at=ended.isoformat(),
        observer_restarts=int(restarted),
        restart_test="PERFORMED" if restarted else "NOT_TESTED",
        wall_seconds=time.monotonic() - began,
        cpu_seconds=time.process_time() - cpu,
        polls=polls,
        processing_budget_misses=misses,
        python_peak_bytes=tracemalloc.get_traced_memory()[1],
        memory_basis="PYTHON_ALLOCATIONS_NOT_PROCESS_RSS",
        latency_basis="GUARDS_HEALTH_AND_OBSERVER_STEP_EXCLUDES_JOURNAL_AND_TARGET_QUERY",
        connectivity_basis="SAMPLED_AT_POLLS; BETWEEN_POLL_DISCONNECTS_NOT_OBSERVABLE",
        continuous_observed_seconds=time.monotonic() - began,
        latency_seconds=dict(
            min=min(ordered) if ordered else None,
            median=ordered[len(ordered) // 2] if ordered else None,
            p95=ordered[round((len(ordered) - 1) * 0.95)] if ordered else None,
            max=max(ordered) if ordered else None,
        ),
        origin=origin,
        qualification="NOT_YET_QUALIFIED",
    )
    try:
        result["db_size_bytes_end"] = db_size(engine)
    except Exception:
        result["db_size_bytes_end"] = None
    journal.record("STOP", result)
    if tracing_owned:
        tracemalloc.stop()
    return result
