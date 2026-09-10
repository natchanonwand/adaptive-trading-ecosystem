"""Phase 1 only: account heads, immutable events, database append-only guard."""

import sqlalchemy as sa
from alembic import op

revision = "0001_journal"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_heads",
        sa.Column("account_id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.CheckConstraint("sequence >= 0", name="ck_head_sequence"),
    )
    op.create_table(
        "journal_events",
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("journal_heads.account_id"), primary_key=True
        ),
        sa.Column("account_sequence", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.CheckConstraint("account_sequence > 0", name="ck_event_sequence"),
    )
    op.execute("""
        CREATE FUNCTION deny_journal_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'journal events are append only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER journal_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON journal_events
        FOR EACH STATEMENT EXECUTE FUNCTION deny_journal_rewrite()
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive journal downgrade is not supported")
