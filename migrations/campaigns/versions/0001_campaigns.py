"""Minimum resumable campaign ledger with append-only run outcomes and audit."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_campaigns"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_campaigns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "definition_id",
            sa.String(),
            sa.ForeignKey("workbench.experiment_definitions.id"),
            unique=True,
        ),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )


def downgrade() -> None:
    raise RuntimeError("Campaign execution evidence cannot be deleted")
