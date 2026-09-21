from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from trading_ecosystem.accounting.contracts import AccountInput
from trading_ecosystem.domain.primitives import Asset
from trading_ecosystem.portfolio.contracts import Book, Economics, Fill, Observation, Quote
from trading_ecosystem.risk.contracts import Health, Request, TradeIntent

T = datetime(2026, 9, 16, tzinfo=UTC)
D = Decimal


def economics(**updates: Any) -> Economics:
    return Economics.model_validate(
        {
            "instrument_id": "fixture-BTC",
            "asset": Asset.BTCUSD,
            "version": "fixture-v1",
            "tick_size": "0.01",
            "tick_value_per_lot": "1",
            "contract_size": "1",
            "usd_per_price_unit_per_lot": "100",
            "volume_min": "0.01",
            "volume_max": "100",
            "volume_step": "0.01",
            "margin_per_lot": "10",
            "commission_per_lot_per_side": "0",
            "commission_fixed_per_side": "0",
            "minimum_stop_distance": "0",
            "valid_from": T - timedelta(days=1),
            "valid_until": T + timedelta(days=10),
            "validation_reference": "SYNTHETIC_ONLY",
            **updates,
        }
    )


def book(**updates: Any) -> Book:
    return Book(
        cash=AccountInput.model_validate(
            {
                "account_id": UUID(int=34001),
                "opening_at": T,
                "opening_cash": "10000",
                "valuation_at": T,
                "reconciled_at": T,
                **updates,
            }
        )
    )


def quote(**updates: Any) -> Quote:
    return Quote.model_validate(
        {
            "quote_id": "fixture-quote",
            "instrument_id": "fixture-BTC",
            "at": T + timedelta(seconds=1),
            "bid": "99.98",
            "ask": "100",
            **updates,
        }
    )


def request(**updates: Any) -> Request:
    initial = book()
    current = book(valuation_at=T + timedelta(seconds=1), reconciled_at=T + timedelta(seconds=1))
    intent = TradeIntent(
        intent_id=UUID(int=34002),
        strategy_id=UUID(int=34003),
        asset=Asset.BTCUSD,
        direction="LONG",
        signal_at=T,
        expires_at=T + timedelta(minutes=5),
        signal_close=D("100"),
        atr=D("1"),
        fixed_stop=D("99"),
    )
    health = Health(
        account_kind="SIMULATED",
        broker_connected=True,
        reconciled=True,
        lease_valid=True,
        approval_valid=True,
        session_open=True,
        calendar_validated=True,
        protection_confirmed=True,
        unknown_submission=False,
    )
    return Request.model_validate(
        {
            "intent": intent,
            "mode": "BACKTEST",
            "at": T + timedelta(seconds=1),
            "health": health,
            "economics": economics(),
            "quote": quote(),
            "history": (Observation(book=initial), Observation(book=current)),
            **updates,
        }
    )


def fill(index: int = 1, **updates: Any) -> Fill:
    return Fill.model_validate(
        {
            "fill_id": UUID(int=34100 + index),
            "realized_entry_id": UUID(int=34200 + index),
            "commission_entry_id": UUID(int=34300 + index),
            "account_id": UUID(int=34001),
            "episode_id": UUID(int=34400),
            "strategy_id": UUID(int=34003),
            "asset": Asset.BTCUSD,
            "direction": "LONG",
            "action": "INCREASE",
            "side": "BUY",
            "quantity": "0.10",
            "actual_price": "100",
            "fixed_stop": "99",
            "actual_commission": "0",
            "at": T + timedelta(seconds=index),
            "economics": economics(),
            **updates,
        }
    )
