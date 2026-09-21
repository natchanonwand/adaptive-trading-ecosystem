"""Telemetry storage metadata, separate from the frozen operational journal."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(schema="monitoring")
heads = Table(
    "telemetry_heads",
    metadata,
    Column("stream_id", Uuid, primary_key=True),
    Column("scope", JSONB, nullable=False),
    Column("sequence", BigInteger, nullable=False),
    Column("event_hash", String(64), nullable=False),
)
sources = Table(
    "telemetry_source_heads",
    metadata,
    Column("stream_id", Uuid, ForeignKey("telemetry_heads.stream_id"), primary_key=True),
    Column("source_instance_id", Uuid, primary_key=True),
    Column("source", String(32), nullable=False),
    Column("sequence", BigInteger, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
)
events = Table(
    "telemetry_events",
    metadata,
    Column("stream_id", Uuid, ForeignKey("telemetry_heads.stream_id"), primary_key=True),
    Column("sequence", BigInteger, primary_key=True),
    Column("event_id", Uuid, unique=True, nullable=False),
    Column("source_instance_id", Uuid, nullable=False),
    Column("source_sequence", BigInteger, nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("body", Text, nullable=False),
    UniqueConstraint(
        "stream_id", "source_instance_id", "source_sequence", name="uq_telemetry_delivery"
    ),
)


def projection_table(name: str) -> Table:
    return Table(
        name,
        metadata,
        Column("stream_id", Uuid, ForeignKey("telemetry_heads.stream_id"), primary_key=True),
        Column("entity_id", String(128), primary_key=True),
        Column("sequence", BigInteger, nullable=False),
        Column("event_id", Uuid, ForeignKey("telemetry_events.event_id"), nullable=False),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
        Column("body", JSONB, nullable=False),
        Column("body_hash", String(64), nullable=False),
    )


account_snapshots = projection_table("account_snapshots")
portfolio_snapshots = projection_table("portfolio_snapshots")
position_projection = projection_table("position_projection")
risk_projection = projection_table("risk_projection")
system_health_projection = projection_table("system_health_projection")
trade_projection = projection_table("trade_projection")
activity_projection = projection_table("activity_projection")
PROJECTIONS = (
    account_snapshots,
    portfolio_snapshots,
    position_projection,
    risk_projection,
    system_health_projection,
    trade_projection,
    activity_projection,
)
