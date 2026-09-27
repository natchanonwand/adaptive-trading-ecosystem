"""Add bounded baseline runs and normalized result identities."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_baselines"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "baseline_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("workbench.projects.id"), nullable=False
        ),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )
    op.create_table(
        "baseline_results",
        sa.Column("id", sa.String(), sa.ForeignKey("workbench.baseline_runs.id"), primary_key=True),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )


def downgrade() -> None:
    raise RuntimeError("Baseline evidence deletion requires explicit retention review")
