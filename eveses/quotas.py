"""
Quotas namespace — remaining prepaid balances. Hits `/api/v1/quotas`. Only
products with a decrementing counter appear (trial / proxy GB / webunblocker
requests); a key is omitted when the user has none.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


class Quotas:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    def all(self) -> Dict[str, Any]:
        """Remaining prepaid balances across trial / proxy / webunblocker."""
        res = self._client.request("GET", "/api/v1/quotas")
        return res if isinstance(res, dict) else {}

    __call__ = all
