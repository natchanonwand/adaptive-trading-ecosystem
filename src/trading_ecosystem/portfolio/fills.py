"""Append-only fill accounting with replay deduplication and no reversal."""

from decimal import Decimal

from trading_ecosystem.accounting.contracts import Category, LedgerEntry
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.portfolio.contracts import Book, Fill, FillReceipt, Position


def apply_fill(book: Book, fill: Fill) -> Book:
    book, fill = Book.model_validate(book), Fill.model_validate(fill)
    for receipt in book.receipts:
        if receipt.fill_id == fill.fill_id:
            if receipt.content_id != fill.identity:
                raise ValueError("CONFLICTING_DUPLICATE_FILL")
            return book
    if fill.account_id != book.cash.account_id or fill.at < book.cash.valuation_at:
        raise ValueError("FILL_ACCOUNT_OR_TIME_MISMATCH")
    economics = fill.economics
    if (
        not economics.validation_reference
        or not economics.valid_from <= fill.at < economics.valid_until
    ):
        raise ValueError("UNVALIDATED_FILL_ECONOMICS")
    if fill.episode_id in book.closed_episodes:
        raise ValueError("CLOSED_EPISODE_REOPENED")
    positions = {p.episode_id: p for p in book.positions}
    previous = positions.get(fill.episode_id)
    if previous is not None and (
        previous.direction != fill.direction
        or previous.strategy_id != fill.strategy_id
        or previous.economics != fill.economics
        or previous.fixed_stop != fill.fixed_stop
    ):
        raise ValueError("FILL_EPISODE_LINEAGE_MISMATCH")
    closed = book.closed_episodes
    with arithmetic_context():
        realized = Decimal(0)
        if fill.action == "INCREASE":
            if previous is not None and previous.reducing:
                raise ValueError("ENTRY_AFTER_REDUCTION_REQUIRES_RECONCILIATION")
            qty = fill.quantity + (previous.quantity if previous else Decimal(0))
            weighted = (
                (previous.quantity * previous.weighted_entry if previous else Decimal(0))
                + fill.quantity * fill.actual_price
            ) / qty
            positions[fill.episode_id] = Position(
                episode_id=fill.episode_id,
                strategy_id=fill.strategy_id,
                asset=fill.asset,
                direction=fill.direction,
                economics=economics,
                quantity=qty,
                weighted_entry=weighted,
                fixed_stop=fill.fixed_stop,
            )
        else:
            if previous is None or fill.quantity > previous.quantity:
                raise ValueError("REDUCTION_WOULD_REVERSE_OR_HAS_NO_POSITION")
            sign = Decimal(1) if fill.direction == "LONG" else Decimal(-1)
            realized = (
                sign
                * (fill.actual_price - previous.weighted_entry)
                * fill.quantity
                * (economics.usd_per_price_unit_per_lot)
            )
            remaining = previous.quantity - fill.quantity
            if remaining:
                positions[fill.episode_id] = previous.model_copy(
                    update={"quantity": remaining, "reducing": True}
                )
            else:
                del positions[fill.episode_id]
                closed += (fill.episode_id,)
        ledger = list(book.cash.ledger)
        for identifier, category, amount in (
            (fill.realized_entry_id, Category.REALIZED_PNL, realized),
            (fill.commission_entry_id, Category.COMMISSION, fill.actual_commission),
        ):
            ledger.append(
                LedgerEntry(
                    entry_id=identifier,
                    account_id=fill.account_id,
                    sequence=len(ledger) + 1,
                    amount=amount,
                    category=category,
                    reference_id=fill.fill_id,
                    effective_at=fill.at,
                    recorded_at=fill.at,
                )
            )
        return Book(
            cash=book.cash.model_copy(
                update={"ledger": tuple(ledger), "valuation_at": fill.at, "reconciled_at": fill.at}
            ),
            positions=tuple(
                sorted(positions.values(), key=lambda p: (p.asset.value, str(p.episode_id)))
            ),
            receipts=(*book.receipts, FillReceipt(fill_id=fill.fill_id, content_id=fill.identity)),
            closed_episodes=closed,
        )
