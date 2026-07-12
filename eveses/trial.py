"""
Trial namespace. Query and subscribe to free-trial access for individual
services. Hits `/api/v1/trial/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


class Trial:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    def status(self) -> Dict[str, Any]:
        """Return the trial status for all services (eligibility, used, expires_at)."""
        res = self._client.request("GET", "/api/v1/trial")
        return res if isinstance(res, dict) else {}

    def subscribe(self, services: List[str]) -> Dict[str, Any]:
        """Activate free-trial access for the given service slugs."""
        res = self._client.request(
            "POST",
            "/api/v1/trial/subscribe",
            json_body={"services": services},
        )
        return res if isinstance(res, dict) else {}
