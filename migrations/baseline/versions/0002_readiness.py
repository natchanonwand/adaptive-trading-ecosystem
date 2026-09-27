"""Add independent append-only attestations and immutable baseline specifications."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_readiness"
down_revision = "0001_baselines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, key, target in (
        ("candidate_authorizations", "candidate_id", "workbench.candidates.id"),
        ("baseline_configurations", "project_id", "workbench.projects.id"),
    ):
        op.create_table(
            name,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(key, sa.String(), sa.ForeignKey(target), nullable=False),
            sa.Column("body", JSONB(), nullable=False),
            schema="workbench",
        )


def downgrade() -> None:
    raise RuntimeError("Immutable readiness evidence cannot be deleted by downgrade")
