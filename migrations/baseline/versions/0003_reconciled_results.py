"""Separate append-only reconciled publication from execution-time baseline results."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_reconciled_results"
down_revision = "0002_readiness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciled_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("workbench.baseline_runs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )


def downgrade() -> None:
    raise RuntimeError("Immutable reconciled publications cannot be deleted by downgrade")
