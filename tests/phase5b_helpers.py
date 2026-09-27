"""Synthetic baseline fixtures; bytes are never executable MT5 artifacts."""

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from trading_ecosystem.tester.adapter import Environment
from trading_ecosystem.tester.contracts import Configuration

EA = b"Synthetic opaque fixture; not executable and not a real EA"


def config(**changes: Any) -> Configuration:
    body = dict(
        baseline_run_id=uuid4(),
        project_id=uuid4(),
        symbol="XAUUSDm",
        timeframe="H1",
        from_date="2026-09-01",
        to_date="2026-09-08",
        initial_deposit="10000",
        leverage=100,
    )
    body.update(changes)
    return Configuration.model_validate(body)


def report(expert: str) -> bytes:
    return (
        Path("tests/fixtures/phase5b_report.htm")
        .read_text(encoding="utf-8")
        .replace("EXPERT_ID", expert)
        .encode()
    )


def environment(root: Path) -> Environment:
    installation = root / "installation"
    installation.mkdir(parents=True)
    terminal = installation / "terminal64.exe"
    terminal.write_bytes(b"Synthetic terminal; never execute")
    (installation / "metatester64.exe").write_bytes(b"Synthetic tester; never execute")
    cache = root / "cache"
    for folder, filename in (("history", "2026.hcc"), ("ticks", "202609.tkc")):
        directory = cache / "Synthetic-Demo" / folder / "XAUUSDm"
        directory.mkdir(parents=True)
        (directory / filename).write_bytes(b"Synthetic cache; not real market data")
    (cache / "Synthetic-Demo" / "symbols.raw").write_bytes(b"Synthetic symbol cache")
    return Environment(
        terminal_executable=terminal,
        terminal_sha256=hashlib.sha256(terminal.read_bytes()).hexdigest(),
        cache_directory=cache,
        broker_name="Synthetic demo",
        server="Synthetic-Demo",
        terminal_build="9999",
    )
