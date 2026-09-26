"""Opaque artifact, candidate and stable research project metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_projects"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("body", JSONB(), nullable=False),
        sa.UniqueConstraint("sha256", "role"),
        schema="workbench",
    )
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("body", JSONB(), nullable=False),
        schema="workbench",
    )


def downgrade() -> None:
    raise RuntimeError("Research metadata downgrade requires explicit retention review")
