from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
)

metadata = MetaData()

journal_heads = Table(
    "journal_heads",
    metadata,
    Column("account_id", Uuid, primary_key=True),
    Column("sequence", BigInteger, nullable=False),
    Column("event_hash", String(64), nullable=False),
    CheckConstraint("sequence >= 0", name="ck_head_sequence"),
)

journal_events = Table(
    "journal_events",
    metadata,
    Column("account_id", Uuid, ForeignKey("journal_heads.account_id"), primary_key=True),
    Column("account_sequence", BigInteger, primary_key=True),
    Column("event_id", Uuid, unique=True, nullable=False),
    Column("event_hash", String(64), nullable=False),
    Column("body", Text, nullable=False),
    CheckConstraint("account_sequence > 0", name="ck_event_sequence"),
)
