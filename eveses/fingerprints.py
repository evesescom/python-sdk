"""
Fingerprints namespace. Resells 2captcha's Fingerprint API, billed pay-per-use
from the wallet (count-on-success). Unlike captcha-solving this is synchronous:
one request returns a complete fingerprint. Hits `/api/account/fingerprints/*`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


@dataclass
class Fingerprint:
    fingerprint: Dict[str, Any] = field(default_factory=dict)
    price_micro_usd: Optional[int] = None


class Fingerprints:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    def generate(self, params: Optional[Dict[str, Any]] = None) -> Fingerprint:
        """Generate a browser fingerprint from the given filter params."""
        return self._request("/api/account/fingerprints/generate", params)

    def random(self, params: Optional[Dict[str, Any]] = None) -> Fingerprint:
        """Fetch a random fingerprint, optionally narrowed by filter params."""
        return self._request("/api/account/fingerprints/random", params)

    def _request(self, path: str, params: Optional[Dict[str, Any]]) -> Fingerprint:
        res = self._client.request("POST", path, json_body=params or {})
        res = res if isinstance(res, dict) else {}
        price = res.get("price_micro_usd")
        return Fingerprint(
            fingerprint=res.get("fingerprint") or {},
            price_micro_usd=int(price) if isinstance(price, int) else None,
        )
