"""The sole gross, realized-only USD 300 / 0.25% illustration."""

from decimal import Decimal
from typing import Any

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.portfolios.accounting import drawdown, periods
from trading_ecosystem.portfolios.contracts import SCENARIO, ZERO, Episode, Interval
from trading_ecosystem.portfolios.events import events


def synthetic(episodes: tuple[Episode, ...], interval: Interval) -> dict[str, Any]:
    with arithmetic_context():
        initial = Decimal(SCENARIO.initial_equity_usd)
        equity, reserved = initial, ZERO
        maximum_cash = maximum_fraction = ZERO
        opened: dict[str, tuple[Episode, Decimal]] = {}
        rejected: set[str] = set()
        ledger: list[dict[str, Any]] = []
        points, cash_points = [], []
        wins = losses = 0
        for time, _, _, _, identifier, kind, episode in events(episodes):
            if kind == "ENTRY":
                risk = equity * Decimal(SCENARIO.risk_fraction)
                reason = None
                if equity <= 0:
                    reason = "NONPOSITIVE_REALIZED_EQUITY"
                elif any(item.asset == episode.asset for item, _ in opened.values()):
                    reason = "SAME_ASSET_CONCURRENCY"
                elif len(opened) >= SCENARIO.max_concurrent:
                    reason = "MAX_CONCURRENCY"
                elif reserved + risk > equity * Decimal(SCENARIO.aggregate_risk_cap) + Decimal(
                    SCENARIO.cash_tolerance
                ):
                    reason = "AGGREGATE_RESERVED_RISK_CAP"
                if reason:
                    rejected.add(identifier)
                    ledger.append(
                        {
                            "time": time,
                            "episode_id": identifier,
                            "asset": episode.asset,
                            "event": "SYNTHETIC_RISK_REJECTED",
                            "reason": reason,
                            "realized_equity": equity,
                            "reserved_risk": reserved,
                        }
                    )
                    continue
                opened[identifier] = (episode, risk)
                reserved = sum((amount for _, amount in opened.values()), ZERO)
                ledger.append(
                    {
                        "time": time,
                        "episode_id": identifier,
                        "asset": episode.asset,
                        "event": "ENTRY",
                        "risk_cash_at_entry": risk,
                        "realized_equity": equity,
                        "reserved_risk": reserved,
                    }
                )
            else:
                if identifier in rejected:
                    continue
                if identifier not in opened or episode.gross_price_R is None:
                    raise ValueError("SYNTHETIC_EXIT_WITHOUT_ACCEPTED_ENTRY")
                _, risk = opened.pop(identifier)
                cash = episode.gross_price_R * risk
                equity += cash
                reserved = sum((amount for _, amount in opened.values()), ZERO)
                wins += cash > 0
                losses += cash < 0
                points.append((time, equity))
                cash_points.append((time, cash))
                ledger.append(
                    {
                        "time": time,
                        "episode_id": identifier,
                        "asset": episode.asset,
                        "event": "EXIT",
                        "risk_cash_at_entry": risk,
                        "gross_cash_pnl": cash,
                        "realized_equity": equity,
                        "reserved_risk": reserved,
                    }
                )
            maximum_cash = max(maximum_cash, reserved)
            if equity > 0:
                maximum_fraction = max(maximum_fraction, reserved / equity)
        horizon = max([interval.end, *(time for time, _ in points)])
        return {
            "scenario": SCENARIO.model_dump(),
            "starting_equity": initial,
            "ending_realized_equity": equity,
            "gross_synthetic_pnl": equity - initial,
            "gross_synthetic_return_fraction": equity / initial - 1,
            "drawdown": drawdown(points, interval.start, horizon, initial),
            "max_reserved_risk_usd": maximum_cash,
            "max_reserved_risk_fraction": maximum_fraction,
            "risk_rejections": len(rejected),
            "open_accepted_episodes": len(opened),
            "wins": wins,
            "losses": losses,
            "ledger": ledger,
            **periods(cash_points, interval),
            "label": "GROSS_SYNTHETIC_NOT_BROKER_EXECUTABLE",
            "missing": [
                "SPREAD UNMODELED",
                "COMMISSION UNMODELED/ASSUMED ZERO",
                "SLIPPAGE ASSUMED ZERO",
                "FINANCING ASSUMED ZERO",
                "NO LOT-SIZE FEASIBILITY HAS BEEN APPLIED.",
                "NO MARGIN MODEL",
                "NO LEVERAGE MODEL",
                "NO MARK-TO-MARKET",
            ],
        }
