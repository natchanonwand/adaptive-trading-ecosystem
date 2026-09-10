"""Search suggestions are never approval, even when names match exactly."""

import re
from collections.abc import Sequence

from trading_ecosystem.discovery.contracts import Instrument, SymbolCandidate
from trading_ecosystem.domain.primitives import Asset


def discover_candidates(instruments: Sequence[Instrument]) -> tuple[SymbolCandidate, ...]:
    result = []
    for asset in Asset:
        candidates = []
        for item in instruments:
            name = re.sub(r"[^A-Z0-9]", "", item.broker_symbol.upper())
            description = (item.description or "").upper()
            matches = {
                Asset.BTCUSD: "BTCUSD" in name
                or (
                    "BITCOIN" in description
                    and "BITCOIN CASH" not in description
                    and item.currency_profit == "USD"
                ),
                Asset.XAUUSD: "XAUUSD" in name
                or ("GOLD" in description and item.currency_profit == "USD"),
                Asset.USTEC100: any(
                    term in name for term in ("USTEC", "NAS100", "US100", "NASDAQ", "NDX", "NQ100")
                )
                or "NASDAQ" in description,
            }
            if matches[asset]:
                candidates.append(item)
        for item in sorted(candidates, key=lambda item: item.broker_symbol):
            result.append(
                SymbolCandidate(
                    **item.model_dump(),
                    canonical_asset=asset,
                    match_basis="EXACT_NAME"
                    if item.broker_symbol == asset.value
                    else "SEARCH_CANDIDATE",
                    reason="AMBIGUOUS_OWNER_APPROVAL_REQUIRED"
                    if len(candidates) > 1
                    else "OWNER_APPROVAL_REQUIRED",
                )
            )
    return tuple(result)
