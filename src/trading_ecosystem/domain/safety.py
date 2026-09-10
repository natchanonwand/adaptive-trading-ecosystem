"""Phase 1 deliberately grants no entry capability."""

from typing import Literal, Protocol

from trading_ecosystem.domain.primitives import Asset, FrozenModel, RuntimeMode


class EntryDecision(FrozenModel):
    enabled: Literal[False] = False
    reason: Literal["PHASE_1_DISABLED"] = "PHASE_1_DISABLED"


class EntryPermission(Protocol):
    def can_open_new_entry(self, *, asset: Asset, mode: RuntimeMode) -> EntryDecision: ...


class DisabledEntryPermission:
    def can_open_new_entry(self, *, asset: Asset, mode: RuntimeMode) -> EntryDecision:
        return EntryDecision()
