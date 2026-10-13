"""Qualification cannot manufacture readiness or consume a campaign reservation."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from trading_ecosystem.tester import portable_qualification as probe
from trading_ecosystem.tester.contracts import Configuration


def configuration() -> Configuration:
    return Configuration(
        baseline_run_id=uuid4(),
        project_id=uuid4(),
        symbol="XAUUSDm",
        timeframe="M5",
        from_date=date(2026, 1, 5),
        to_date=date(2026, 1, 6),
        initial_deposit=Decimal("300"),
        leverage=100,
        timeout_seconds=60,
        input_provenance="USER_CONFIRMED_VALUES",
        set_text=probe.INPUTS,
    )


def test_exact_baseline_inputs_and_probe_interval() -> None:
    probe.validate_inputs(configuration())


@pytest.mark.parametrize(
    "update",
    [
        {"set_text": "InpFastEmaPeriod=10\nInpSlowEmaPeriod=100\n"},
        {"set_text": "InpFastEmaPeriod=100\nInpSlowEmaPeriod=20\n"},
        {"timeframe": "M1"},
        {"symbol": "BTCUSDm"},
        {"from_date": date(2026, 5, 16)},
        {"timeout_seconds": 600},
    ],
)
def test_other_inputs_and_oos_rejected(update: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="BLOCKED_QUALIFICATION_CONFIG"):
        probe.validate_inputs(configuration().model_copy(update=update))


def test_wrong_artifact_rejected_before_native_work(tmp_path: Path) -> None:
    source = Path(probe.__file__).parent.parent / "experiments/ReferenceEmaCrossM5.mq5"
    artifact = tmp_path / "wrong.ex5"
    artifact.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="BLOCKED_ARTIFACT_IDENTITY_MISMATCH"):
        probe.run(tmp_path / "probe", artifact)
    assert not (tmp_path / "probe").exists()
    assert probe.sha(source.resolve()) == probe.SOURCE


@pytest.mark.parametrize(
    "text,status",
    [
        ("no account", "ACCOUNT_CONTEXT_FAILURE"),
        ("MQL5.community authorization failed", "UNKNOWN_INITIALIZATION_FAILURE"),
        ("tester not started because the account is not specified", "ACCOUNT_CONTEXT_FAILURE"),
        ("OnInit failed", "EXPERT_ONINIT_FAILURE"),
        ("generating based on real ticks", "UNKNOWN_INITIALIZATION_FAILURE"),
        ("", "UNKNOWN_INITIALIZATION_FAILURE"),
    ],
)
def test_observations_cannot_manufacture_qualification(text: str, status: str) -> None:
    result = probe.assess(text, True)
    assert result["status"] == status
    assert result["campaign_authorization"] == "NOT_AUTHORIZED"
    assert result["start_eligible"] is False
    assert result["full_interval_real_tick_coverage"] == "UNKNOWN"
    assert "net_profit" not in result


def test_relative_staging_path_rejected() -> None:
    with pytest.raises(ValueError, match="BLOCKED_UNSAFE_TERMINAL_PATH"):
        probe.sha(Path("../escape.ex5"))
