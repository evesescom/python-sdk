"""
Web Unblocker namespace. Buy and manage a web-unblocker subscription (metered
by request count). Hits `/api/v1/webunblocker/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


class WebUnblocker:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------------ read --
    def pricing(self) -> Dict[str, Any]:
        """Available web-unblocker request packages (price tiers, per-request cost)."""
        return self._get("/api/v1/webunblocker/pricing")

    def quote(self, requests: int, *, subscription: bool = False) -> Dict[str, Any]:
        """Estimate a purchase before buying."""
        params: Dict[str, Any] = {"requests": requests}
        if subscription:
            params["subscription"] = 1
        return self._get("/api/v1/webunblocker/quote", params=params)

    def access(self) -> Dict[str, Any]:
        """Return the current web-unblocker access details (credentials, endpoints)."""
        return self._get("/api/v1/webunblocker/orders")

    # ----------------------------------------------------------------- write --
    def purchase(
        self,
        requests: int,
        *,
        subscription: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Buy a web-unblocker request bundle (or start a subscription)."""
        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        body: Dict[str, Any] = {"requests": requests}
        if subscription:
            body["subscription"] = True

        res = self._client.request(
            "POST",
            "/api/v1/webunblocker/orders",
            json_body=body,
            headers=headers or None,
        )
        return res if isinstance(res, dict) else {}

    def trial(self) -> Dict[str, Any]:
        """Activate the web-unblocker free trial (one-time per account)."""
        res = self._client.request("POST", "/api/v1/webunblocker/trial")
        return res if isinstance(res, dict) else {}

    def subscription_cancel(self) -> Dict[str, Any]:
        """Cancel the web-unblocker subscription."""
        return self._subscription_action("cancel")

    def subscription_pause(self) -> Dict[str, Any]:
        """Pause the web-unblocker subscription."""
        return self._subscription_action("pause")

    def subscription_resume(self) -> Dict[str, Any]:
        """Resume the web-unblocker subscription."""
        return self._subscription_action("resume")

    # --------------------------------------------------------------- helpers --
    def _subscription_action(self, action: str) -> Dict[str, Any]:
        res = self._client.request(
            "POST", f"/api/v1/webunblocker/subscription/{action}"
        )
        return res if isinstance(res, dict) else {}

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self._client.request("GET", path, params=params)
        return res if isinstance(res, dict) else {}
