"""Finite, deterministic calculator/domain experiments; never persists risk reservations."""

import math
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import product
from uuid import UUID

from trading_ecosystem.accounting.contracts import AccountInput
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.mt5.calculations import Calculator, Side
from trading_ecosystem.mt5.calibration_economics import (
    conditional_economics,
    constraints,
    valid_volume,
)
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.economics import BrokerInstrumentSnapshot
from trading_ecosystem.mt5.normalization import number
from trading_ecosystem.portfolio.contracts import (
    Book,
    Economics,
    Observation,
    Position,
    Quote,
)
from trading_ecosystem.portfolio.projection import _mark
from trading_ecosystem.risk.contracts import Health, Policy, Request, TradeIntent
from trading_ecosystem.risk.engine import evaluate

SIDES: tuple[Side, ...] = ("BUY", "SELL")
MOVEMENTS = (-100, -10, -1, 1, 10, 100)
STOP_TICKS = (100, 10000, 200000, 500000)
EQUITIES = (Decimal("300"), Decimal("3000"), Decimal("30000"))
POLICIES = (Policy(), Policy(policy_id="HR_DEMO_5PCT"))


def tolerance(e: Economics, volume: Decimal, prices: tuple[Decimal, ...], digits: int) -> Decimal:
    """Two half-unit monetary leg roundings plus propagated double roundoff.

    Four ULPs per input conservatively bound binary input conversion and native
    price subtraction. This is microscopic relative to one tick, not a fitted limit.
    """
    with arithmetic_context():
        binary = sum((Decimal(str(math.ulp(float(p)))) for p in prices), Decimal(0))
        return Decimal(1).scaleb(-digits) + 4 * binary * volume * e.contract_size


def rounding_predictions(
    e: Economics, side: Side, volume: Decimal, opened: Decimal, closed: Decimal, digits: int
) -> set[Decimal]:
    """Test both net rounding and separately rounded legs; tolerate only binary ties.

    Actual DEMO probes show separate monetary-leg rounding for BTC and gold.
    The one-unit bound is the sum of two half-unit errors, not an empirical fit.
    Candidate membership additionally rejects unexplained errors within that bound.
    """
    with arithmetic_context():
        quantum = Decimal(1).scaleb(-digits)
        epsilon = tolerance(e, volume, (opened, closed), digits) - quantum
        sign = 1 if side == "BUY" else -1
        start = opened * volume * e.contract_size
        end = closed * volume * e.contract_size
        offsets = (-epsilon, Decimal(0), epsilon)
        net = {
            ((end - start) * sign + offset).quantize(quantum, ROUND_HALF_UP) for offset in offsets
        }
        legs = {
            (end + x).quantize(quantum, ROUND_HALF_UP) * sign
            - (start + y).quantize(quantum, ROUND_HALF_UP) * sign
            for x, y in product(offsets, offsets)
        }
        return net | legs


def domain_pnl(
    e: Economics, side: Side, volume: Decimal, opened: Decimal, closed: Decimal
) -> Decimal:
    at = e.valid_from
    position = Position(
        episode_id=UUID(int=1),
        strategy_id=UUID(int=2),
        asset=e.asset,
        direction="LONG" if side == "BUY" else "SHORT",
        economics=e,
        quantity=volume,
        weighted_entry=opened,
        fixed_stop=opened,
    )
    source = Observation(
        book=Book(
            cash=AccountInput(
                account_id=UUID(int=3),
                opening_at=at,
                opening_cash=Decimal("300"),
                valuation_at=at,
                reconciled_at=at,
            ),
            positions=(position,),
        ),
        quotes=(
            Quote(
                quote_id="CALIBRATION_ONLY",
                instrument_id=e.instrument_id,
                at=at,
                bid=closed,
                ask=closed,
            ),
        ),
    )
    with arithmetic_context():
        result = _mark(source)[0].unrealized_pnl
    if result is None:
        raise ValueError("DOMAIN_PNL_UNAVAILABLE")
    return result


def risk_request(
    e: Economics, side: Side, quote: Record, equity: Decimal, stop_ticks: int, policy: Policy
) -> Request:
    with arithmetic_context():
        at = e.valid_from + timedelta(seconds=1)
        bid, ask = number(quote["bid"]), number(quote["ask"])
        entry = ask if side == "BUY" else bid
        distance = e.tick_size * stop_ticks
        stop = entry - distance if side == "BUY" else entry + distance
        midnight = at.replace(hour=0, minute=0, second=0, microsecond=0)
        initial = Book(
            cash=AccountInput(
                account_id=UUID(int=3),
                opening_at=midnight,
                opening_cash=equity,
                valuation_at=midnight,
                reconciled_at=midnight,
            )
        )
        current = Book(
            cash=initial.cash.model_copy(update={"valuation_at": at, "reconciled_at": at})
        )
        return Request(
            intent=TradeIntent(
                intent_id=UUID(int=4),
                strategy_id=UUID(int=2),
                asset=e.asset,
                direction="LONG" if side == "BUY" else "SHORT",
                signal_at=e.valid_from,
                expires_at=e.valid_until,
                signal_close=entry,
                atr=max(distance, (ask - bid) * 20, e.tick_size),
                fixed_stop=stop,
            ),
            policy=policy,
            mode="BACKTEST",
            at=at,
            health=Health(
                account_kind="SIMULATED",
                broker_connected=True,
                reconciled=True,
                lease_valid=True,
                approval_valid=True,
                session_open=True,
                calendar_validated=True,
                protection_confirmed=True,
                unknown_submission=False,
            ),
            economics=e,
            quote=Quote(
                quote_id="FROZEN_CALIBRATION_QUOTE",
                instrument_id=e.instrument_id,
                at=at,
                bid=bid,
                ask=ask,
            ),
            history=(Observation(book=initial), Observation(book=current)),
        )


def risk_matrix(
    calculator: Calculator,
    e_by_side: dict[Side, Economics],
    quote: Record,
    digits: int,
    observed_free_margin: Decimal,
) -> list[Record]:
    rows = []
    with arithmetic_context():
        for side, ticks, equity, policy in product(SIDES, STOP_TICKS, EQUITIES, POLICIES):
            e = e_by_side[side]
            req = risk_request(e, side, quote, equity, ticks, policy)
            decision = evaluate(req)
            entry = req.intent.signal_close
            stop = req.intent.fixed_stop
            minimum_loss = -calculator.profit(side, e.instrument_id, e.volume_min, entry, stop)
            budget = equity * Decimal(policy.limits[0])
            order = decision.order
            row: Record = {
                "side": side,
                "stop_ticks": ticks,
                "equity": str(equity),
                "policy": policy.policy_id,
                "requested_risk": policy.limits[0],
                "risk_budget": str(budget),
                "entry": str(entry),
                "stop": str(stop),
                "minimum_lot_broker_loss": str(minimum_loss),
                "selected_volume": None,
                "predicted_loss": None,
                "broker_loss": None,
                "difference": None,
                "accepted": decision.accepted,
                "reasons": list(decision.reasons),
                "decision_identity": decision.identity,
                "qualification_eligible": False,
            }
            if minimum_loss > budget + tolerance(e, e.volume_min, (entry, stop), digits):
                if decision.accepted:
                    raise ValueError("MINIMUM_LOT_BUDGET_BREACH")
            if order is not None:
                loss = -calculator.profit(side, e.instrument_id, order.volume, entry, stop)
                margin = calculator.margin(side, e.instrument_id, order.volume, entry)
                tol = tolerance(e, order.volume, (entry, stop), digits)
                # The margin model is conservative over sampled rounding; no budget widening.
                if loss > budget + tol or loss > order.estimated_stop_risk + tol:
                    raise ValueError("BROKER_STOP_LOSS_EXCEEDS_ALLOWED_RISK")
                if order.estimated_stop_risk > budget:
                    raise ValueError("DOMAIN_STOP_LOSS_EXCEEDS_ALLOWED_RISK")
                if margin > equity * Decimal("0.20") + Decimal(1).scaleb(-digits) / 2:
                    raise ValueError("BROKER_MARGIN_EXCEEDS_SIMULATED_CAP")
                row.update(
                    selected_volume=str(order.volume),
                    predicted_loss=str(order.estimated_stop_risk),
                    broker_loss=str(loss),
                    difference=str(order.estimated_stop_risk - loss),
                    tolerance=str(tol),
                    broker_incremental_margin_estimate=str(margin),
                    predicted_margin=str(order.estimated_margin),
                    simulated_free_margin=str(equity),
                    simulated_margin_cap=str(equity * Decimal(".20")),
                    within_simulated_free_margin=margin <= equity,
                    observed_account_free_margin=str(observed_free_margin),
                    within_observed_free_margin=margin <= observed_free_margin,
                )
            rows.append(row)
    return rows


def calibrate_symbol(
    calculator: Calculator,
    snapshot: BrokerInstrumentSnapshot,
    quote: Record,
    digits: int,
    observed_free_margin: Decimal,
) -> Record:
    if type(digits) is not int or not 0 <= digits <= 8:
        raise ValueError("CURRENCY_PRECISION_REQUIRED")
    stop_metadata = constraints(snapshot)
    m = snapshot.metadata
    with arithmetic_context():
        tick, minimum, step, maximum = (
            number(m[k]) for k in ("trade_tick_size", "volume_min", "volume_step", "volume_max")
        )
        bid, ask = number(quote["bid"]), number(quote["ask"])
        if bid <= 0 or ask < bid or bid % tick or ask % tick:
            raise ValueError("INVALID_QUOTE_LATTICE")
        volumes = sorted(
            {
                v
                for v in (minimum, minimum + step, minimum + 10 * step, Decimal(1))
                if v <= maximum and valid_volume(v, snapshot)
            }
        )
        if len(volumes) < 3:
            raise ValueError("INSUFFICIENT_VOLUME_LATTICE_SAMPLES")
        margins: list[Record] = []
        profits: list[Record] = []
        economics: dict[Side, Economics] = {}
        quantum = Decimal(1).scaleb(-digits)
        for side in SIDES:
            entry = ask if side == "BUY" else bid
            raw = [(v, calculator.margin(side, snapshot.broker_symbol, v, entry)) for v in volumes]
            # Upper bound each rounded observation; conservative local representation.
            per_lot = max((margin + quantum / 2) / v for v, margin in raw)
            reference_volume, reference_margin = raw[-1]
            for v, margin in raw:
                estimate = reference_margin / reference_volume * v
                tol = quantum / 2 * (1 + v / reference_volume)
                if margin < 0 or abs(margin - estimate) > tol:
                    raise ValueError("NONLINEAR_MARGIN_NOT_REPRESENTABLE")
                margins.append(
                    {
                        "side": side,
                        "volume": str(v),
                        "price": str(entry),
                        "broker_incremental_margin_estimate": str(margin),
                        "linear_reference_estimate": str(estimate),
                        "tolerance": str(tol),
                        "conservative_margin_per_lot": str(per_lot),
                    }
                )
            e = conditional_economics(snapshot, per_lot)
            economics[side] = e
            for volume, movement in product(volumes, MOVEMENTS):
                closed = entry + tick * movement
                if closed <= 0:
                    raise ValueError("NONPOSITIVE_SYNTHETIC_CLOSE")
                broker = calculator.profit(side, snapshot.broker_symbol, volume, entry, closed)
                domain = domain_pnl(e, side, volume, entry, closed)
                error = abs(broker - domain)
                tol = tolerance(e, volume, (entry, closed), digits)
                predictions = rounding_predictions(e, side, volume, entry, closed, digits)
                if broker not in predictions:
                    raise ValueError("UNEXPLAINED_BROKER_MONETARY_ROUNDING")
                if error > tol:
                    raise ValueError(
                        f"BROKER_DOMAIN_PNL_MISMATCH symbol={snapshot.broker_symbol} "
                        f"side={side} volume={volume} ticks={movement} broker={broker} "
                        f"domain={domain} error={error} tolerance={tol}"
                    )
                profitable = (movement > 0) == (side == "BUY")
                field = "trade_tick_value_profit" if profitable else "trade_tick_value_loss"
                tick_prediction = abs(movement) * volume * number(m[field])
                if abs(abs(broker) - tick_prediction) > tol:
                    raise ValueError("BROKER_TICK_ECONOMICS_MISMATCH")
                profits.append(
                    {
                        "side": side,
                        "volume": str(volume),
                        "movement_ticks": movement,
                        "price_open": str(entry),
                        "price_close": str(closed),
                        "broker_calculated_pnl": str(broker),
                        "domain_calculated_pnl": str(domain),
                        "absolute_error": str(error),
                        "relative_error": str(error / abs(domain)) if domain else None,
                        "tolerance": str(tol),
                        "rounding_predictions": [str(p) for p in sorted(predictions)],
                        "tick_value_field": field,
                        "tick_value_predicted_magnitude": str(tick_prediction),
                    }
                )
        risk_rows = risk_matrix(calculator, economics, quote, digits, observed_free_margin)
        for policy in POLICIES:
            if not any(r["accepted"] and r["policy"] == policy.policy_id for r in risk_rows):
                raise ValueError("FEASIBLE_RISK_COVERAGE_INCOMPLETE")
        return {
            "logical_symbol": snapshot.logical_symbol,
            "broker_symbol": snapshot.broker_symbol,
            "metadata": m,
            "quote": quote,
            "stop_constraints": stop_metadata,
            "tested_volumes": [str(v) for v in volumes],
            "profit_rows": profits,
            "profit_calculation_count": len(profits),
            "profit_max_absolute_error": str(max(number(r["absolute_error"]) for r in profits)),
            "margin_rows": margins,
            "risk_rows": risk_rows,
        }
