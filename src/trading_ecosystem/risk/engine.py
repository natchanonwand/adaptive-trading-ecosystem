"""Deterministic admission, exact lot lattice search and latched risk status."""

from datetime import timedelta
from decimal import Decimal

from trading_ecosystem.accounting.contracts import Category
from trading_ecosystem.accounting.performance import _ratio_at_most
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.portfolio.contracts import Observation, Reservation
from trading_ecosystem.portfolio.projection import Snapshot, project
from trading_ecosystem.risk.contracts import Decision, OrderIntent, Request, RiskState

ZERO = Decimal(0)


def _loss_reasons(snapshot: Snapshot, daily: Decimal, drawdown: Decimal) -> list[str]:
    reasons = []
    day, nav = snapshot.risk_day, snapshot.nav
    if day.today_trading_pnl is not None and day.boundary_equity is not None:
        n, d = daily.copy_negate().as_integer_ratio()
        if _ratio_at_most(day.today_trading_pnl, day.boundary_equity, n, d):
            reasons.append("DAILY_LOSS_HALT")
    if nav.nav is not None and nav.high_water_mark is not None:
        n, d = (Decimal(1) - drawdown).as_integer_ratio()
        if _ratio_at_most(nav.nav, nav.high_water_mark, n, d):
            reasons.append("DRAWDOWN_HALT")
    return reasons


def _state(request: Request, snapshot: Snapshot) -> RiskState:
    policy = request.policy
    _, _, day_limit, dd_limit, _ = policy.limits
    cash = snapshot.source.book.cash
    prior = request.prior_state
    if prior is not None and (
        prior.account_id != cash.account_id or prior.policy != policy or prior.at > request.at
    ):
        raise ValueError("PRIOR_RISK_STATE_LINEAGE_MISMATCH")
    halted: list[str] = []
    if prior is not None and prior.status == "HALT_AND_FLATTEN":
        halted.extend(prior.reasons)
    # Missing prior state cannot hide an earlier breach present in supplied history.
    for index in range(1, len(request.history) + 1):
        historical = snapshot if index == len(request.history) else project(request.history[:index])
        halted.extend(_loss_reasons(historical, Decimal(day_limit), Decimal(dd_limit)))
        # Evaluate the closing UTC day before a midnight observation becomes
        # the next day's baseline. A rollover cannot erase an observed breach.
        if index > 1:
            previous = project(request.history[: index - 1])
            old_day = previous.risk_day
            if (
                historical.risk_day.boundary_at > old_day.boundary_at
                and historical.accounting.equity is not None
                and not historical.accounting.stale
                and old_day.unavailable_reason is None
                and old_day.boundary_equity is not None
            ):
                boundary = next(
                    o for o in request.history if o.book.cash.valuation_at == old_day.boundary_at
                )
                flows = sum(
                    (
                        e.amount
                        for e in historical.source.book.cash.ledger[
                            len(boundary.book.cash.ledger) :
                        ]
                        if e.category == Category.CASH_FLOW
                    ),
                    ZERO,
                )
                closing_pnl = historical.accounting.equity - old_day.boundary_equity - flows
                n, d = Decimal(day_limit).copy_negate().as_integer_ratio()
                if _ratio_at_most(closing_pnl, old_day.boundary_equity, n, d):
                    halted.append("DAILY_LOSS_HALT_AT_ROLLOVER")
    if request.health.severe_breach:
        halted.append("SEVERE_RECONCILIATION_OR_RISK_BREACH")
    reasons = []
    health = request.health
    if policy.policy_id == "V0_CONSERVATIVE" and any(
        p.direction == "SHORT" for p in snapshot.source.book.positions
    ):
        reasons.append("V0_SHORT_EXPOSURE_REQUIRES_RECONCILIATION")
    if health.account_kind in {"REAL", "UNKNOWN"}:
        reasons.append("ACCOUNT_TYPE_REJECTED")
    if request.mode.value.startswith("DEMO") and health.account_kind != "DEMO":
        reasons.append("CONFIRMED_DEMO_ACCOUNT_REQUIRED")
    if policy.policy_id == "HR_DEMO_5PCT" and request.mode.value not in {
        "BACKTEST",
        "PAPER_FORWARD",
        "DEMO_QUALIFICATION",
    }:
        reasons.append("EXPERIMENTAL_MODE_FORBIDDEN")
    for healthy, reason in (
        (health.broker_connected, "BROKER_DISCONNECTED"),
        (health.reconciled, "RECONCILIATION_UNHEALTHY"),
        (health.lease_valid, "LEASE_INVALID"),
        (health.approval_valid, "APPROVAL_INVALID"),
        (health.session_open and health.calendar_validated, "SESSION_OR_CALENDAR_UNKNOWN"),
        (health.protection_confirmed, "PROTECTION_UNCONFIRMED"),
        (not health.unknown_submission, "UNKNOWN_SUBMISSION"),
    ):
        if not healthy:
            reasons.append(reason)
    if request.at < cash.valuation_at or request.at - cash.reconciled_at > timedelta(seconds=15):
        reasons.append("STALE_OR_FUTURE_ACCOUNT")
    if snapshot.accounting.stale or not snapshot.accounting.complete:
        reasons.append("PORTFOLIO_VALUATION_UNTRUSTED")
    if snapshot.nav.unavailable_reason or snapshot.risk_day.unavailable_reason:
        reasons.append("UNKNOWN_NAV_OR_DAILY_BASELINE")
    if snapshot.accounting.equity is None or snapshot.accounting.equity <= 0:
        reasons.append("NONPOSITIVE_OR_UNKNOWN_EQUITY")
    quote = request.quote
    if quote is None or not timedelta(0) <= request.at - quote.at <= timedelta(seconds=5):
        reasons.append("STALE_OR_MISSING_QUOTE")
    # Existing marks also age at decision time, not just at projection time.
    if any(request.at - q.at > timedelta(seconds=5) for q in snapshot.source.quotes):
        reasons.append("STALE_PORTFOLIO_MARK")
    return RiskState(
        account_id=cash.account_id,
        policy=policy,
        at=request.at,
        status="HALT_AND_FLATTEN" if halted else "PAUSE_ENTRIES" if reasons else "ACTIVE",
        reasons=tuple(dict.fromkeys(halted + reasons)),
    )


def evaluate(request: Request) -> Decision:
    request = Request.model_validate(request)
    with arithmetic_context():
        snapshot = project(request.history)
        state = _state(request, snapshot)
        identity = request.identity

        def reject(*reasons: str) -> Decision:
            return Decision(
                state=state,
                accepted=False,
                reasons=tuple(reasons),
                input_identity=identity,
                snapshot_identity=snapshot.identity,
                order=None,
                reservation=None,
            )

        if state.status != "ACTIVE":
            return reject(*state.reasons)
        intent, economics, quote = request.intent, request.economics, request.quote
        if request.policy.policy_id == "V0_CONSERVATIVE" and intent.direction != "LONG":
            return reject("V0_LONG_ONLY")
        if not intent.signal_at < request.at < intent.expires_at:
            return reject("ENTRY_NOT_AFTER_SIGNAL_OR_EXPIRED")
        if economics is None or not economics.validation_reference:
            return reject("MISSING_VALIDATED_ECONOMICS")
        if not economics.valid_from <= request.at < economics.valid_until:
            return reject("EXPIRED_ECONOMICS")
        assert quote is not None
        if economics.asset != intent.asset or quote.instrument_id != economics.instrument_id:
            return reject("INSTRUMENT_MISMATCH")
        if any(p.asset == intent.asset for p in snapshot.source.book.positions) or any(
            r.asset == intent.asset for r in snapshot.source.reservations
        ):
            return reject("ASSET_OCCUPIED")
        trade_limit, aggregate_limit, _, _, max_positions = request.policy.limits
        if len(snapshot.source.book.positions) + len(snapshot.source.reservations) >= max_positions:
            return reject("POSITION_COUNT_LIMIT")
        if quote.ask - quote.bid > intent.atr * Decimal("0.10"):
            return reject("SPREAD_LIMIT")
        entry = quote.ask if intent.direction == "LONG" else quote.bid
        sign = Decimal(1) if intent.direction == "LONG" else Decimal(-1)
        distance = sign * (entry - intent.fixed_stop)
        if distance <= 0 or distance < economics.minimum_stop_distance:
            return reject("INVALID_FIXED_STOP")
        # Require the supplied fixed stop to be on the zero-origin price lattice.
        pn, pd = intent.fixed_stop.as_integer_ratio()
        tn, td = economics.tick_size.as_integer_ratio()
        if (pn * td) % (pd * tn):
            return reject("STOP_OFF_TICK_LATTICE")
        if sign * (entry - intent.signal_close) > intent.atr * Decimal("0.25"):
            return reject("ADVERSE_ENTRY_MOVEMENT")
        equity = snapshot.accounting.equity
        assert equity is not None and snapshot.open_risk is not None
        assert snapshot.used_margin is not None and snapshot.gross_exposure is not None
        open_risk, used_margin, gross_exposure = (
            snapshot.open_risk,
            snapshot.used_margin,
            snapshot.gross_exposure,
        )
        budget = equity * Decimal(trade_limit)
        risk_per_lot = (
            distance + 2 * economics.tick_size
        ) * economics.usd_per_price_unit_per_lot + 2 * economics.commission_per_lot_per_side
        fixed_cost = 2 * economics.commission_fixed_per_side

        def costs(volume: Decimal) -> tuple[Decimal, Decimal, Decimal]:
            return (
                volume * risk_per_lot + fixed_cost,
                volume * economics.margin_per_lot,
                volume * entry * economics.contract_size,
            )

        def failures(volume: Decimal) -> tuple[str, ...]:
            risk, margin, notional = costs(volume)
            failed = []
            if risk > budget:
                failed.append("NEW_EPISODE_RISK_LIMIT")
            if open_risk + snapshot.reserved_risk + risk > equity * Decimal(aggregate_limit):
                failed.append("AGGREGATE_RISK_LIMIT")
            if used_margin + snapshot.reserved_margin + margin > equity * Decimal("0.20"):
                failed.append("MARGIN_LIMIT")
            if gross_exposure + snapshot.reserved_exposure + notional > equity * 2:
                failed.append("GROSS_NOTIONAL_LIMIT")
            return tuple(failed)

        if problems := failures(economics.volume_min):
            return reject(*problems)
        # Exact integer search over min + n*step; never divide a risk budget and round up.
        mn, md = economics.volume_max.as_integer_ratio()
        ln, ld = economics.volume_min.as_integer_ratio()
        sn, sd = economics.volume_step.as_integer_ratio()
        lower, upper = 0, ((mn * ld - ln * md) * sd) // (md * ld * sn)
        experimental = request.policy.policy_id == "HR_DEMO_5PCT"
        while lower < upper:
            middle = (lower + upper + 1) // 2
            volume = economics.volume_min + middle * economics.volume_step
            feasible = costs(volume)[0] <= budget if experimental else not failures(volume)
            if feasible:
                lower = middle
            else:
                upper = middle - 1
        volume = economics.volume_min + lower * economics.volume_step
        vn, vd = volume.as_integer_ratio()
        if (vn * ld - ln * vd) * sd % (vd * ld * sn):
            return reject("VOLUME_LATTICE_EXCEEDS_DECIMAL_PRECISION")
        if not economics.volume_min <= volume <= economics.volume_max:
            return reject("VOLUME_OUTSIDE_BROKER_RANGE")
        if problems := failures(volume):
            return reject(*problems)
        risk, margin, notional = costs(volume)
        order = OrderIntent(
            trade_intent=intent,
            volume=volume,
            reference_entry=entry,
            fixed_stop=intent.fixed_stop,
            estimated_stop_risk=risk,
            estimated_margin=margin,
            gross_notional=notional,
            expires_at=min(
                request.at + timedelta(seconds=5),
                intent.expires_at,
                economics.valid_until,
                quote.at + timedelta(seconds=5),
                snapshot.source.book.cash.reconciled_at + timedelta(seconds=15),
            ),
            input_identity=identity,
        )
        if order.expires_at <= request.at:
            return reject("NO_VALID_APPROVAL_LIFETIME")
        reservation = Reservation(
            reservation_id=order.identity,
            intent_id=intent.intent_id,
            strategy_id=intent.strategy_id,
            asset=intent.asset,
            direction=intent.direction,
            volume=volume,
            stop_risk=risk,
            margin=margin,
            gross_notional=notional,
            decision_id=identity,
        )
        return Decision(
            state=state,
            accepted=True,
            reasons=(),
            input_identity=identity,
            snapshot_identity=snapshot.identity,
            order=order,
            reservation=reservation,
        )


def evaluate_and_reserve(request: Request) -> tuple[Decision, tuple[Observation, ...]]:
    """Pure serial reservation transition. Caller must persist with compare-and-swap.

    Reservations never expire/release automatically; reconciliation owns release.
    """
    decision = evaluate(request)
    if decision.reservation is None:
        return decision, request.history
    current = request.history[-1]
    updated = current.model_copy(
        update={"reservations": (*current.reservations, decision.reservation)}
    )
    return decision, (*request.history[:-1], updated)
