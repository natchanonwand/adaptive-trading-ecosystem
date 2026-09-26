"""Fault-injected controller tests, isolated from MT5 and persistent real evidence."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

from tests.campaigns.test_campaigns import specification
from tests.observer.fixtures import FakeObserver, T
from trading_ecosystem.campaigns import runtime
from trading_ecosystem.campaigns.finalize import ready
from trading_ecosystem.campaigns.journal import read


@pytest.mark.parametrize(
    "fault,expected",
    [
        (None, "STOPPED_RECONCILED"),
        ("step", "PAUSED"),
        ("account", "INVALIDATED"),
        ("real", "INVALIDATED"),
        ("disconnect", "PAUSED"),
        ("gap", "DEGRADED"),
        ("stop", "PAUSED"),
        ("reconcile", "PAUSED"),
        ("health", "PAUSED"),
        ("interrupt", "PAUSED"),
    ],
)
def test_foreground_controller_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None, expected: str
) -> None:
    elapsed = [0.0]
    calls = [0]
    guards = [0]
    instances: list[Any] = []

    class Clock:
        @staticmethod
        def now(*args: Any) -> Any:
            return T + timedelta(seconds=elapsed[0])

    class SoftwareObserver:
        recovered = False
        last_history: object = "initial"

        def __init__(self, *args: Any) -> None:
            instances.append(self)
            self.recovered = len(instances) > 1

        def step(self, at: Any) -> bool:
            calls[0] += 1
            elapsed[0] += 7 if fault == "gap" else 0.1
            if fault == "interrupt":
                raise KeyboardInterrupt
            return fault != "step" and not (fault == "reconcile" and self.last_history is None)

        def stop(self, at: Any) -> None:
            if fault == "stop":
                raise RuntimeError("software test DB unavailable")

    def guard(*args: Any) -> dict[str, Any]:
        guards[0] += 1
        if guards[0] > 1 and fault in ("account", "real", "disconnect"):
            raise ValueError(
                {
                    "account": "INVALIDATED_ACCOUNT_SWITCH",
                    "real": "INVALIDATED_ACCOUNT_NOT_DEMO",
                    "disconnect": "MT5_DISCONNECTED",
                }[fault]
            )
        return {}

    monkeypatch.setattr(runtime, "datetime", Clock)
    monkeypatch.setattr("trading_ecosystem.campaigns.runtime.time.monotonic", lambda: elapsed[0])
    monkeypatch.setattr(
        "trading_ecosystem.campaigns.runtime.time.sleep",
        lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
    )
    monkeypatch.setattr(runtime, "NativeObserverClient", FakeObserver)
    monkeypatch.setattr(runtime, "Observer", SoftwareObserver)
    monkeypatch.setattr(runtime, "account_guard", guard)
    monkeypatch.setattr(runtime, "db_size", lambda engine: 100)
    monkeypatch.setattr(
        runtime,
        "inspect_health",
        lambda *args: {
            "passed": not (fault == "health" and elapsed[0] >= 5),
            "checks": {"test_only": True},
        },
    )
    engine = create_engine("sqlite://")
    path = tmp_path / "SOFTWARE_TEST_ONLY"
    try:
        result = runtime.run(specification(), FakeObserver(), engine, path, restart_after_seconds=2)
        assert result["status"] == expected
        assert read(path)[-1]["kind"] == "STOP"
        assert not (path / "raw").exists() and not (path / "features").exists()
        if fault is None:
            assert result["observer_restarts"] == 1
            assert result["polls"] > 1
            assert result["restart_test"] == "PERFORMED"
            assert ready(path)[1] == result
        else:
            with pytest.raises(ValueError):
                ready(path)
    finally:
        engine.dispose()
