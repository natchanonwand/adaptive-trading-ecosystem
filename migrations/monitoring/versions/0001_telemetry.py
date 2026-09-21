"""Append-only telemetry source records and rebuildable read models."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_telemetry"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry_heads",
        sa.Column("stream_id", sa.Uuid(), primary_key=True),
        sa.Column("scope", JSONB(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.CheckConstraint("sequence >= 0", name="ck_telemetry_head_sequence"),
        schema="monitoring",
    )
    op.create_table(
        "telemetry_source_heads",
        sa.Column(
            "stream_id",
            sa.Uuid(),
            sa.ForeignKey("monitoring.telemetry_heads.stream_id"),
            primary_key=True,
        ),
        sa.Column("source_instance_id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_telemetry_source_sequence"),
        schema="monitoring",
    )
    op.create_table(
        "telemetry_events",
        sa.Column(
            "stream_id",
            sa.Uuid(),
            sa.ForeignKey("monitoring.telemetry_heads.stream_id"),
            primary_key=True,
        ),
        sa.Column("sequence", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("source_instance_id", sa.Uuid(), nullable=False),
        sa.Column("source_sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "stream_id", "source_instance_id", "source_sequence", name="uq_telemetry_delivery"
        ),
        sa.CheckConstraint(
            "sequence > 0 AND source_sequence > 0", name="ck_telemetry_event_sequence"
        ),
        schema="monitoring",
    )
    op.execute("""CREATE FUNCTION monitoring.deny_telemetry_rewrite()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'telemetry events are append only'; END; $$""")
    op.execute("""CREATE TRIGGER telemetry_append_only BEFORE UPDATE OR DELETE OR TRUNCATE
        ON monitoring.telemetry_events FOR EACH STATEMENT
        EXECUTE FUNCTION monitoring.deny_telemetry_rewrite()""")
    for name in (
        "account_snapshots",
        "portfolio_snapshots",
        "position_projection",
        "risk_projection",
        "system_health_projection",
        "trade_projection",
        "activity_projection",
    ):
        op.create_table(
            name,
            sa.Column(
                "stream_id",
                sa.Uuid(),
                sa.ForeignKey("monitoring.telemetry_heads.stream_id"),
                primary_key=True,
            ),
            sa.Column("entity_id", sa.String(128), primary_key=True),
            sa.Column("sequence", sa.BigInteger(), nullable=False),
            sa.Column(
                "event_id",
                sa.Uuid(),
                sa.ForeignKey("monitoring.telemetry_events.event_id"),
                nullable=False,
            ),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("body", JSONB(), nullable=False),
            sa.Column("body_hash", sa.String(64), nullable=False),
            schema="monitoring",
        )
        op.create_index(
            "ix_" + name + "_cursor", name, ["stream_id", "sequence"], schema="monitoring"
        )


def downgrade() -> None:
    raise RuntimeError("Destructive telemetry downgrade is not supported")
