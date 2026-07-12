"""
Orders namespace — the global, cross-product order history. Hits
`/api/v1/orders`. Returns a normalized OrderView for numbers / proxy /
webunblocker / emails (captcha is NOT here — see `client.captcha.usage()`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


class Orders:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    def list(
        self,
        *,
        service: Optional[str] = None,
        status: Optional[str] = None,
        created_gte: Optional[str] = None,
        created_lte: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Cursor-paginated global order history, newest first.

        ``service`` accepts a comma-separated subset of
        ``numbers,proxy,webunblocker,emails``.
        """
        params: Dict[str, Any] = {}
        if service is not None:
            params["service"] = service
        if status is not None:
            params["status"] = status
        if created_gte is not None:
            params["created[gte]"] = created_gte
        if created_lte is not None:
            params["created[lte]"] = created_lte
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        res = self._client.request("GET", "/api/v1/orders", params=params or None)
        return res if isinstance(res, dict) else {}

    def get(self, uuid: str) -> Dict[str, Any]:
        """Fetch the normalized OrderView for any single order (any product)."""
        res = self._client.request("GET", f"/api/v1/orders/{uuid}")
        return res if isinstance(res, dict) else {}
