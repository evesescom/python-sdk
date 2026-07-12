"""
Emails namespace. Buy and manage temporary email addresses, browse received
messages. Hits `/api/v1/emails/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


class Emails:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------------ read --
    def pricing(self, *, site: Optional[str] = None) -> Dict[str, Any]:
        """List available email domains + prices (domains under the ``domains`` key)."""
        params: Dict[str, Any] = {}
        if site is not None:
            params["site"] = site
        return self._get("/api/v1/emails/pricing", params=params or None)

    def quote(
        self,
        domain: str,
        *,
        site: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Estimate the cost of a temporary email purchase."""
        params: Dict[str, Any] = {"domain": domain}
        if site is not None:
            params["site"] = site
        if provider is not None:
            params["provider"] = provider
        return self._get("/api/v1/emails/quote", params=params)

    def list(self, *, include_released: bool = False) -> Dict[str, Any]:
        """List owned temporary email addresses."""
        params: Dict[str, Any] = {}
        if include_released:
            params["include_released"] = 1
        return self._get("/api/v1/emails/orders", params=params or None)

    def get(self, email: str) -> Dict[str, Any]:
        """Fetch a single email address (inbox metadata)."""
        return self._get(f"/api/v1/emails/{email}")

    def messages(
        self, email: str, *, page: int = 1, per_page: int = 20
    ) -> Dict[str, Any]:
        """Paginate received messages for an email address."""
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        return self._get(f"/api/v1/emails/{email}/messages", params=params)

    # ----------------------------------------------------------------- write --
    def purchase(
        self,
        domain: str,
        *,
        site: Optional[str] = None,
        provider: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Buy a temporary email address."""
        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        body: Dict[str, Any] = {"domain": domain}
        if site is not None:
            body["site"] = site
        if provider is not None:
            body["provider"] = provider

        res = self._client.request(
            "POST",
            "/api/v1/emails/orders",
            json_body=body,
            headers=headers or None,
        )
        return res if isinstance(res, dict) else {}

    def mark_read(self, email: str, message_id: int) -> Dict[str, Any]:
        """Mark a received message as read."""
        res = self._client.request(
            "POST",
            f"/api/v1/emails/{email}/messages/{message_id}/read",
        )
        return res if isinstance(res, dict) else {}

    def release(self, email: str) -> Dict[str, Any]:
        """Release (delete) a temporary email address."""
        res = self._client.request("DELETE", f"/api/v1/emails/{email}")
        return res if isinstance(res, dict) else {}

    # --------------------------------------------------------------- helpers --
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self._client.request("GET", path, params=params)
        return res if isinstance(res, dict) else {}
