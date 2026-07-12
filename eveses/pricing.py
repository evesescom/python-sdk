"""
Pricing namespace — all product prices in one call. Hits `/api/v1/pricing`
(numbers / proxy / webunblocker / emails / captcha). Per-service prices are
also available on each product module (e.g. `client.proxy.pricing()`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


class Pricing:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    def all(self) -> Dict[str, Any]:
        """Aggregate price sheet across every product, keyed by service."""
        res = self._client.request("GET", "/api/v1/pricing")
        return res if isinstance(res, dict) else {}

    # Allow ``client.pricing()``-style call via the module accessor too.
    __call__ = all
