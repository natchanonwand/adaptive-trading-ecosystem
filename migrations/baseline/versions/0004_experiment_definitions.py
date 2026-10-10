"""Pre-registered immutable research definitions and protocol-violation evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_experiment_definitions"
down_revision = "0003_reconciled_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_definitions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("workbench.projects.id"), nullable=False
        ),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )
    op.create_table(
        "experiment_protocol_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "definition_id",
            sa.String(),
            sa.ForeignKey("workbench.experiment_definitions.id"),
            nullable=False,
        ),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )


def downgrade() -> None:
    raise RuntimeError("Immutable experiment definitions and protocol evidence cannot be deleted")
