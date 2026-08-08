"""
Proxy namespace. Buy and manage residential (metered, per-GB) and static
(per-IP: ISP / datacenter / IPv6 / sneaker / mobile) proxies. Hits
`/api/v1/proxy/*`.

The provider stays invisible: connection details are returned under the
white-label host.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


@dataclass
class ProxyOrder:
    uuid: str
    type: str
    status: str
    price_cents: int
    currency: str = "USD"
    kind: Optional[str] = None
    gb: Optional[float] = None
    quantity: Optional[int] = None
    location: Optional[str] = None
    proxies: Any = None
    auto_extend: bool = False
    extendable: bool = False
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProxySubscription:
    status: str
    gb: float = 0.0
    discount_pct: int = 0
    next_renews_at: Optional[str] = None
    renew_failures: int = 0


@dataclass
class ProxyList:
    residential: Optional[Dict[str, Any]]
    subscription: Optional[ProxySubscription]
    orders: List[ProxyOrder]


class Proxy:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------------ read --
    def pricing(self) -> Dict[str, Any]:
        """All proxy prices: residential GB ladder + static per-IP catalogue."""
        return self._get("/api/v1/proxy/pricing")

    def endpoints(self) -> Dict[str, Any]:
        """White-label connection endpoints: regional subdomains + HTTP/SOCKS5 ports."""
        return self._get("/api/v1/proxy/endpoints")

    def locations(self, type: str = "residential") -> Dict[str, Any]:
        """
        Available targeting for a proxy type: residential geo (countries/regions/
        sets) or a static family's catalogue locations.
        """
        return self._get("/api/v1/proxy/locations", params={"type": type})

    def locations_detail(self, country: str, type: str = "residential") -> Dict[str, Any]:
        """
        Per-country residential state/city/ISP geo drill-down.

        Returns ``{type, country, geo: {country, states: [{code, name, cities?}],
        cities: [{code, name, isps?}], tokens: {country, city, state, isp}}}``.
        """
        return self._get(
            "/api/v1/proxy/locations/detail", params={"type": type, "country": country}
        )

    def quote(
        self,
        *,
        type: str = "residential",
        gb: Optional[float] = None,
        subscription: bool = False,
        product_id: Optional[int] = None,
        plan_id: Optional[int] = None,
        location_id: Optional[int] = None,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Estimate a purchase before buying (residential GB or a static selection)."""
        params: Dict[str, Any] = {"type": type}
        if type == "residential":
            params["gb"] = gb if gb is not None else 0
            if subscription:
                params["subscription"] = "true"
        else:
            params["product_id"] = product_id
            params["plan_id"] = plan_id
            params["location_id"] = location_id
            params["quantity"] = quantity
        return self._get("/api/v1/proxy/quote", params=params)

    def usage(self, *, from_: Optional[str] = None, to: Optional[str] = None) -> Dict[str, Any]:
        """Residential usage analytics — daily traffic/requests timeline + top hosts."""
        params: Dict[str, Any] = {}
        if from_ is not None:
            params["from"] = from_
        if to is not None:
            params["to"] = to
        return self._get("/api/v1/proxy/usage", params=params or None)

    def list(self) -> ProxyList:
        """The user's proxies: residential connection, subscription, per-IP orders."""
        res = self._client.request("GET", "/api/v1/proxy/orders")
        res = res if isinstance(res, dict) else {}

        residential = res.get("residential") if isinstance(res.get("residential"), dict) else None
        subscription = res.get("subscription")
        subscription = self._map_subscription(subscription) if isinstance(subscription, dict) else None
        orders_raw = res.get("orders") if isinstance(res.get("orders"), list) else []
        orders = [self._map_order(o if isinstance(o, dict) else {}) for o in orders_raw]

        return ProxyList(residential=residential, subscription=subscription, orders=orders)

    def get(self, order_uuid: str) -> ProxyOrder:
        """Fetch a single proxy order by UUID."""
        res = self._client.request("GET", f"/api/v1/proxy/orders/{order_uuid}")
        return self._map_order(res if isinstance(res, dict) else {})

    # ----------------------------------------------------------------- write --
    def purchase(
        self,
        *,
        type: str = "residential",
        gb: Optional[float] = None,
        subscription: bool = False,
        product_id: Optional[int] = None,
        plan_id: Optional[int] = None,
        location_id: Optional[int] = None,
        location_name: Optional[str] = None,
        quantity: int = 1,
        idempotency_key: Optional[str] = None,
    ) -> ProxyOrder:
        """Buy proxies (residential GB top-up or static IPs). Returns the order."""
        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        body: Dict[str, Any] = {"type": type}
        if type == "residential":
            body["gb"] = gb if gb is not None else 0
            if subscription:
                body["subscription"] = True
        else:
            body["product_id"] = product_id
            body["plan_id"] = plan_id
            body["location_id"] = location_id
            if location_name is not None:
                body["location_name"] = location_name
            body["quantity"] = quantity

        res = self._client.request(
            "POST",
            "/api/v1/proxy/orders",
            json_body=body,
            headers=headers or None,
        )
        return self._map_order(res if isinstance(res, dict) else {})

    def extend(self, order_uuid: str, days: int = 30) -> ProxyOrder:
        """Extend a static (per-IP) order for another period (re-charges its price)."""
        res = self._client.request(
            "POST",
            f"/api/v1/proxy/orders/{order_uuid}/extend",
            json_body={"days": days},
        )
        return self._map_order(res if isinstance(res, dict) else {})

    def auto_renew(self, order_uuid: str, enabled: bool) -> ProxyOrder:
        """Toggle auto-renew (auto_extend) on a per-IP order."""
        res = self._client.request(
            "POST",
            f"/api/v1/proxy/orders/{order_uuid}/auto-renew",
            json_body={"enabled": enabled},
        )
        return self._map_order(res if isinstance(res, dict) else {})

    def trial(self) -> Dict[str, Any]:
        """Activate the proxy free trial (one-time per account)."""
        res = self._client.request("POST", "/api/v1/proxy/trial")
        return res if isinstance(res, dict) else {}

    def reset_sessions(self) -> Dict[str, Any]:
        """Reset the residential sticky sessions (next request rotates IPs)."""
        res = self._client.request("POST", "/api/v1/proxy/sessions/reset")
        return res if isinstance(res, dict) else {}

    def subscription_cancel(self) -> ProxySubscription:
        """Cancel the residential subscription (stop auto-renewal; traffic stays)."""
        return self._subscription_action("cancel")

    def subscription_pause(self) -> ProxySubscription:
        """Pause the residential subscription (skip renewals until resumed)."""
        return self._subscription_action("pause")

    def subscription_resume(self) -> ProxySubscription:
        """Resume the residential subscription (next renewal a month out)."""
        return self._subscription_action("resume")

    # --------------------------------------------------------------- helpers --
    def _subscription_action(self, action: str) -> ProxySubscription:
        res = self._client.request("POST", f"/api/v1/proxy/subscription/{action}")
        return self._map_subscription(res if isinstance(res, dict) else {})

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self._client.request("GET", path, params=params)
        return res if isinstance(res, dict) else {}

    @staticmethod
    def _map_order(r: Dict[str, Any]) -> ProxyOrder:
        gb = r.get("gb")
        return ProxyOrder(
            uuid=str(r.get("uuid") or ""),
            type=str(r.get("type") or ""),
            status=str(r.get("status") or ""),
            price_cents=int(r.get("price_cents") or 0),
            currency=str(r.get("currency") or "USD"),
            kind=r.get("kind") if isinstance(r.get("kind"), str) else None,
            gb=float(gb) if isinstance(gb, (int, float)) else None,
            quantity=r.get("quantity") if isinstance(r.get("quantity"), int) else None,
            location=r.get("location") if isinstance(r.get("location"), str) else None,
            proxies=r.get("proxies"),
            auto_extend=r.get("auto_extend") is True,
            extendable=r.get("extendable") is True,
            expires_at=r.get("expires_at") if isinstance(r.get("expires_at"), str) else None,
            created_at=r.get("created_at") if isinstance(r.get("created_at"), str) else None,
            raw=r,
        )

    @staticmethod
    def _map_subscription(r: Dict[str, Any]) -> ProxySubscription:
        gb = r.get("gb")
        return ProxySubscription(
            status=str(r.get("status") or ""),
            gb=float(gb) if isinstance(gb, (int, float)) else 0.0,
            discount_pct=int(r.get("discount_pct") or 0),
            next_renews_at=r.get("next_renews_at") if isinstance(r.get("next_renews_at"), str) else None,
            renew_failures=int(r.get("renew_failures") or 0),
        )
