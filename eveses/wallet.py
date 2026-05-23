"""
Wallet namespace. Hits `/api/account/wallet`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


@dataclass
class WalletBalance:
    balance: int
    held_balance: int
    available_balance: int
    currency: str


class Wallet:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    def balance(self) -> WalletBalance:
        """Snapshot of total / held / available balance."""
        res = self._client.request("GET", "/api/account/wallet")
        d = _unwrap(res)
        return WalletBalance(
            balance=_int(d.get("balance"), 0),
            held_balance=_int(d.get("held_balance"), 0),
            available_balance=_int(d.get("available_balance"), 0),
            currency=str(d.get("currency") or "USD"),
        )


def _unwrap(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}


def _int(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default
