"""Explicit algorithm-only fixtures, including simulated real-type guard inputs."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading_ecosystem.behavioral_research.contracts import Record, identity
from trading_ecosystem.behavioral_research.loader import ResearchDataset
from trading_ecosystem.features.registry import CATALOG, FEATURE_SET_ID


def dataset(n: int = 12, *, real_guard: bool = False, aligned: bool = True) -> ResearchDataset:
    xs, ys = [], []
    for i in range(n):
        session = f"algorithm-fixture-session-{i % 3}"
        at = (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i)).isoformat()
        x: Record = {d.name: None for d in CATALOG if d.causal}
        x.update(
            row_id=f"x{i}",
            session_id=session,
            episode_id=f"episode{i}",
            candidate_id="algorithm-fixture-only",
            symbol="FIXTURE",
            direction="BUY" if i % 2 == 0 else "SELL",
            prediction_cutoff=at,
            entry_observed_at=at,
            entry_time_known=True,
            source_confidence="KNOWN",
            entry_volume="1",
            has_SL=True,
            has_TP=True,
            initial_SL_distance="10",
            initial_TP_distance="20",
            m15_stop_distance_atr="2",
            m15_tp_distance_atr="4",
            hour_utc=i % 24,
            day_of_week=i % 7,
            session="UTC_FIXTURE",
            previous_entry_volume="1",
            volume_ratio_vs_previous="1",
            previous_episode_direction="BUY",
            time_since_previous_entry="60",
            price_distance_from_previous_entry="2",
            m15_atr14="5",
            h1_atr14="10",
            h4_atr14="20",
            h1_rsi14="50",
            m15_rsi14=str(20 + i % 60),
            same_direction_sequence_length=1,
            same_direction_open_count=1,
            same_symbol_open_count=1,
        )
        direction = Decimal(1 if i % 2 == 0 else -1) * (1 if aligned else -1)
        for period in (20, 50, 200):
            x[f"h1_ema{period}_distance_atr"] = str(direction)
        y: Record = {
            d.name: [] if d.dtype == "decimal_sequence" else None for d in CATALOG if not d.causal
        }
        y.update(
            row_id=f"y{i}",
            session_id=session,
            episode_id=f"episode{i}",
            available_at=at,
            closed_at=at,
            holding_duration="30",
            episode_entry_count=1,
            increase_count=0,
            entry_volume_sequence=["1"],
            entry_price_sequence=["100"],
            net_observed_pnl="2" if i % 2 else "-2",
            SL_change_count=0,
            TP_change_count=0,
            SL_removed_count=0,
            TP_removed_count=0,
        )
        xs.append(x)
        ys.append(y)
    manifest = dict(
        dataset_type="REAL_DEMO_OBSERVATION" if real_guard else "SYNTHETIC_QUALIFICATION",
        feature_set_id=FEATURE_SET_ID,
        session_ids=sorted({r["session_id"] for r in xs}),
    )
    return ResearchDataset(manifest, identity([manifest, xs, ys]), xs, [], ys)
