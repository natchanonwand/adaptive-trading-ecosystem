"""Deterministic lifecycle and conservative position episodes from immutable frames."""

from decimal import Decimal
from typing import Any

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number, timestamp
from trading_ecosystem.observer.context import context_key
from trading_ecosystem.observer.contracts import (
    Frame,
    LifecycleEvent,
    ObservationSession,
    attribute,
    content_id,
)


def position_key(row: Record) -> str:
    return str(row.get("identifier") or row.get("ticket"))


def replay(
    session: ObservationSession, frames: tuple[Frame, ...]
) -> tuple[list[Record], list[Record]]:
    if any(f.session_id != session.session_id or f.sequence != i + 1 for i, f in enumerate(frames)):
        raise ValueError("OBSERVER_FRAME_SEQUENCE_MISMATCH")
    if any(b.observed_at < a.observed_at for a, b in zip(frames, frames[1:], strict=False)):
        raise ValueError("NONMONOTONIC_OBSERVATION_TIME")
    events: list[Record] = []
    episodes: list[Record] = []

    def emit(
        kind: str,
        row: Record,
        frame: Frame,
        values: Record,
        position: str | None,
        broker: Any = None,
        direct: bool = False,
    ) -> None:
        reference = content_id(frame.model_dump(mode="json"))
        basis = [
            str(session.session_id),
            kind,
            position,
            row.get("ticket"),
            values,
            reference if direct else None,
        ]
        context = frame.contexts.get(
            context_key(str(row.get("symbol", "")), broker or frame.observed_at)
        )
        event = LifecycleEvent(
            event_id=content_id(basis),
            session_id=session.session_id,
            sequence=0,
            kind=kind,
            observed_at=frame.observed_at,
            broker_at=broker,
            quality="DIRECT" if direct else "RECONSTRUCTED",
            recovered_state=frame.recovered,
            attribution=attribute(row, session.config),
            symbol=str(row.get("symbol", "")),
            position_id=position,
            values=values,
            raw_reference=reference,
            context_reference=content_id(context) if context else None,
        )
        events.append(event.model_dump(mode="json"))

    seen_deals: dict[str, tuple[Record, Frame]] = {}
    for frame in frames:
        for row in frame.deals:
            key = str(row["ticket"])
            if key in seen_deals and seen_deals[key][0] != row:
                raise ValueError("CONFLICTING_IMMUTABLE_DEAL")
            seen_deals.setdefault(key, (row, frame))
    ordered = sorted(
        seen_deals.values(),
        key=lambda pair: (
            number(pair[0].get("time_msc", 0)),
            number(pair[0].get("time", 0)),
            pair[0]["ticket"],
        ),
    )
    active: dict[str, Record] = {}
    epochs: dict[str, int] = {}
    initial_positions = {position_key(p) for p in frames[0].positions} if frames else set()
    with arithmetic_context():
        for row, frame in ordered:
            at = timestamp(row["time"], row.get("time_msc"))
            if at > frame.observed_at:
                raise ValueError("FUTURE_BROKER_DEAL")
            pid = str(row.get("position_id", 0))
            emit("DEAL_OBSERVED", row, frame, row, pid, at)
            if row.get("type") not in (0, 1) or pid == "0":
                continue
            volume = number(row["volume"])
            if volume <= 0:
                raise ValueError("NONPOSITIVE_DEAL_VOLUME")
            sign = Decimal(1) if row["type"] == 0 else Decimal(-1)
            before = active.get(pid)
            signed_before = number(before["signed_volume"]) if before else Decimal(0)
            entry = row.get("entry")
            if entry not in (0, 1, 2, 3):
                raise ValueError("UNKNOWN_DEAL_ENTRY_SEMANTICS")
            missing_open = before is None and entry in (1, 2, 3)
            anchor_at = None
            if missing_open:
                anchors = [
                    (f, p)
                    for f in frames
                    if f.observed_at < at
                    for p in f.positions
                    if position_key(p) == pid
                ]
                if anchors:
                    anchor, observed = anchors[-1]
                    signed_before = number(observed["volume"]) * (
                        1 if observed["type"] == 0 else -1
                    )
                    anchor_at = anchor.observed_at
                    missing_open = False
            after = signed_before + sign * volume
            if (entry == 2 and missing_open) or (
                entry in (1, 3)
                and (missing_open or signed_before * sign >= 0 or abs(after) > abs(signed_before))
            ):
                emit(
                    "RECOVERED_STATE",
                    row,
                    frame,
                    {"reason": "EXIT_WITHOUT_SUFFICIENT_OPENING_EVIDENCE", "deal": row},
                    pid,
                    at,
                )
                if before:
                    before["complete"] = False
                continue
            if before is None:
                epochs[pid] = epochs.get(pid, 0) + 1
                before = {
                    "episode_id": content_id([str(session.session_id), pid, epochs[pid]]),
                    "session_id": str(session.session_id),
                    "position_id": pid,
                    "symbol": row["symbol"],
                    "direction": "BUY" if (signed_before or sign) > 0 else "SELL",
                    "attribution": attribute(row, session.config).model_dump(mode="json"),
                    "first_seen_at": frame.observed_at.isoformat(),
                    "opened_at": None if anchor_at else at.isoformat(),
                    "origin": "PREEXISTING" if anchor_at else "BROKER_HISTORY",
                    "opening_time_basis": "UNKNOWN_ENTRY_TIME" if anchor_at else "BROKER_DEAL_TIME",
                    "closed_at": None,
                    "signed_volume": "0",
                    "deal_tickets": [],
                    "entry_volumes": [],
                    "entry_prices": [],
                    "exit_prices": [],
                    "scale_in_count": 0,
                    "partial_close_count": 0,
                    "reversal_count": 0,
                    "gross_pnl": "0",
                    "commission": "0",
                    "fee": "0",
                    "swap": "0",
                    "complete": at >= session.started_at
                    and not missing_open
                    and anchor_at is None
                    and pid not in initial_positions,
                    "episode_confidence": "RECONSTRUCTED",
                    "holding_seconds": None,
                    "mae": None,
                    "mfe": None,
                }
                active[pid] = before
                episodes.append(before)
            attribution = attribute(row, session.config).model_dump(mode="json")
            if attribution != before["attribution"]:
                before["attribution"] = {
                    "source": "UNKNOWN",
                    "confidence": "AMBIGUOUS",
                    "candidate_id": None,
                }
                before["episode_confidence"] = "AMBIGUOUS"
            before["deal_tickets"].append(row["ticket"])
            before["last_seen_at"] = frame.observed_at.isoformat()
            for field, source in (
                ("gross_pnl", "profit"),
                ("commission", "commission"),
                ("fee", "fee"),
                ("swap", "swap"),
            ):
                before[field] = (
                    str(number(before[field]) + number(row[source]))
                    if before[field] is not None and row.get(source) is not None
                    else None
                )
            reversed_side = signed_before != 0 and after * signed_before < 0
            increasing = signed_before == 0 or signed_before * sign > 0
            kind = (
                "POSITION_REVERSED"
                if reversed_side
                else "POSITION_OPENED"
                if signed_before == 0
                else "POSITION_INCREASED"
                if increasing
                else "POSITION_CLOSED"
                if after == 0
                else "POSITION_REDUCED"
            )
            if increasing:
                before["entry_volumes"].append(str(volume))
                before["entry_prices"].append(str(number(row["price"])))
                if signed_before:
                    before["scale_in_count"] += 1
            else:
                before["exit_prices"].append(str(number(row["price"])))
                before["partial_close_count"] += int(after != 0 and not reversed_side)
            before["signed_volume"] = str(after)
            values: Record = {
                "deal_ticket": row["ticket"],
                "order_ticket": row.get("order"),
                "direction": "BUY" if sign > 0 else "SELL",
                "volume": str(volume),
                "price": str(number(row["price"])),
                "old_volume": str(abs(signed_before)),
                "remaining_volume": str(abs(after)),
                "opened_volume": str(abs(after))
                if reversed_side
                else str(volume)
                if increasing
                else "0",
                "closed_volume": str(min(abs(signed_before), volume)) if not increasing else "0",
                "profit": row.get("profit"),
                "commission": row.get("commission"),
                "fee": row.get("fee"),
                "swap": row.get("swap"),
                "account_snapshot_basis": "POLL_TIME_NOT_HISTORICAL_ENTRY",
                "exact_same_timestamp_order": "TICKET_TIEBREAK_NOT_CAUSAL_PROOF",
            }
            fields = [row.get(k) for k in ("profit", "commission", "fee", "swap")]
            values["net_observed_pnl"] = (
                str(sum((number(v) for v in fields), Decimal(0))) if None not in fields else None
            )
            emit(kind, row, frame, values, pid, at)
            if reversed_side:
                before["reversal_count"] += 1
                before["episode_confidence"] = "AMBIGUOUS"
                before["complete"] = False
                # Keep a broker-position episode, explicitly mixed direction; do not allocate fees.
                before["direction"] = "MIXED_REVERSAL"
            if after == 0:
                before["closed_at"] = at.isoformat()
                opened = timestamp_from_text(before["opened_at"]) if before["opened_at"] else None
                before["holding_seconds"] = (
                    str(Decimal(str((at - opened).total_seconds())))
                    if before["complete"] and opened
                    else None
                )
                del active[pid]
        previous_positions: dict[str, Record] = {}
        previous_orders: dict[str, Record] = {}
        historical_orders: dict[str, Record] = {}
        deal_positions = {str(r.get("position_id")) for r, _ in ordered}
        for frame in frames:
            for historical in frame.history_orders:
                key = str(historical["ticket"])
                prior_history = historical_orders.get(key)
                if prior_history != historical:
                    emit(
                        "ORDER_HISTORY_OBSERVED"
                        if prior_history is None
                        else "ORDER_HISTORY_CHANGED",
                        historical,
                        frame,
                        {
                            "old_value": prior_history,
                            "new_value": historical,
                            "fill_inference": "NONE",
                        },
                        None,
                    )
                    historical_orders[key] = historical
            current = {position_key(p): p for p in frame.positions}
            if len(current) != len(frame.positions):
                raise ValueError("DUPLICATE_BROKER_POSITION_ID")
            if session.margin_mode in (0, 1) and len({p["symbol"] for p in frame.positions}) != len(
                current
            ):
                raise ValueError("NETTING_MODE_POSITION_CONTRADICTION")
            for pid, row in current.items():
                prior = previous_positions.get(pid)
                if prior is None:
                    emit(
                        "POSITION_STATE_OBSERVED",
                        row,
                        frame,
                        {
                            **snapshot_values(row, frame),
                            "origin": "RECOVERED" if frame.recovered else "PREEXISTING",
                            "opened_at": None,
                            "holding_seconds": None,
                        },
                        pid,
                        direct=True,
                    )
                elif any(
                    prior.get(k) != row.get(k)
                    for k in ("volume", "type", "price_open", "sl", "tp", "magic", "comment")
                ):
                    if pid not in deal_positions:
                        old, new = number(prior["volume"]), number(row["volume"])
                        kind = (
                            "RECOVERED_STATE"
                            if prior["type"] != row["type"] or new != old
                            else "POSITION_UPDATED"
                        )
                        emit(
                            kind,
                            row,
                            frame,
                            {**snapshot_values(row, frame), "old_volume": str(old)},
                            pid,
                            direct=True,
                        )
                    elif any(prior.get(k) != row.get(k) for k in ("volume", "type", "price_open")):
                        emit(
                            "RECOVERED_STATE",
                            row,
                            frame,
                            {
                                **snapshot_values(row, frame),
                                "reason": "POLL_STATE_RECONCILIATION_NOT_AN_ADDITIONAL_FILL",
                            },
                            pid,
                            direct=True,
                        )
                for field, kind in (("sl", "STOP_LOSS_CHANGED"), ("tp", "TAKE_PROFIT_CHANGED")):
                    old_stop = prior.get(field) if prior else None
                    if row.get(field) != old_stop:
                        emit(
                            kind,
                            row,
                            frame,
                            {
                                "old_value": old_stop,
                                "new_value": row.get(field),
                                "time_basis": "FIRST_OBSERVED_AT",
                                "change": "INITIAL"
                                if prior is None
                                else "REMOVED"
                                if number(row.get(field) or 0) == 0
                                else "CHANGED",
                            },
                            pid,
                            direct=True,
                        )
            for pid, prior in previous_positions.items():
                if pid not in current:
                    emit(
                        "POSITION_REMOVED_OBSERVED",
                        prior,
                        frame,
                        {"reason": "DISAPPEARANCE_IS_NOT_PROOF_OF_FILL", "exit_price": None},
                        pid,
                        direct=True,
                    )
            orders = {str(r["ticket"]): r for r in frame.orders}
            for key, row in orders.items():
                if key not in previous_orders or row != previous_orders[key]:
                    emit(
                        "ORDER_OBSERVED" if key not in previous_orders else "ORDER_CHANGED",
                        row,
                        frame,
                        {"old_value": previous_orders.get(key), "new_value": row},
                        None,
                        direct=True,
                    )
            for key, row in previous_orders.items():
                if key not in orders:
                    emit("ORDER_REMOVED", row, frame, {"fill_status": "UNKNOWN"}, None, direct=True)
            previous_positions, previous_orders = current, orders
    for episode in episodes:
        costs = [episode[k] for k in ("gross_pnl", "commission", "fee", "swap")]
        with arithmetic_context():
            episode["net_observed_pnl"] = (
                str(sum((number(v) for v in costs), Decimal(0))) if None not in costs else None
            )
        episode["ea_metrics_eligible"] = (
            episode["complete"]
            and episode["attribution"]["source"] == "EXTERNAL_EA"
            and episode["attribution"]["confidence"] == "KNOWN"
            and episode["episode_confidence"] != "AMBIGUOUS"
        )
    events.sort(key=lambda e: (e["observed_at"], e["broker_at"] or e["observed_at"], e["event_id"]))
    for index, event in enumerate(events):
        event["sequence"] = index + 1
    return events, sorted(episodes, key=lambda e: e["episode_id"])


def timestamp_from_text(value: str) -> Any:
    from trading_ecosystem.domain.primitives import utc_timestamp

    return utc_timestamp(value)


def snapshot_values(row: Record, frame: Frame) -> Record:
    with arithmetic_context():
        entry, volume = number(row["price_open"]), number(row["volume"])
        sl, tp = number(row.get("sl") or 0), number(row.get("tp") or 0)
        sd, td = abs(entry - sl) if sl else None, abs(entry - tp) if tp else None
        metadata = frame.metadata.get(row["symbol"], {})
        contract = metadata.get("trade_contract_size")
        equity = frame.account.get("equity")
        return {
            "position": row,
            "entry_price": str(entry),
            "volume": str(volume),
            "sl_distance": str(sd) if sd is not None else None,
            "tp_distance": str(td) if td is not None else None,
            "tp_sl_distance_ratio": str(td / sd) if td is not None and sd else None,
            "notional_exposure": str(entry * volume * number(contract)) if contract else None,
            "equity_relative_lots": str(volume / number(equity))
            if equity and number(equity) > 0
            else None,
            "account_equity": equity,
            "account_balance": frame.account.get("balance"),
            "open_position_count": len(frame.positions),
            "same_symbol_gross_lots": str(
                sum(
                    (number(p["volume"]) for p in frame.positions if p["symbol"] == row["symbol"]),
                    Decimal(0),
                )
            ),
            "risk_fraction": None,
            "source_time_basis": "FIRST_OBSERVED_AT",
        }
