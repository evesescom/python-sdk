"""
Proxies namespace — buy and manage residential (metered, GB) and static
(per-IP) proxies. Hits ``/api/account/proxies/*``.

The provider stays invisible: connection details are returned under the
white-label host. Money is always integer cents; ``currency`` is ``"USD"``.

Quote / catalog responses are decoded leniently: the raw wire map is always
preserved under ``.raw`` so new fields surface without an SDK bump.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


# ---------------------------------------------------------------- models --
@dataclass
class ResidentialAccess:
    host: str
    ports: Dict[str, int]
    username: str
    password: str
    example: Optional[str] = None
    curl: Optional[str] = None
    traffic_gb_available: float = 0.0
    traffic_gb_used: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProxySubscription:
    status: str
    gb: float = 0.0
    discount_pct: int = 0
    next_renews_at: Optional[str] = None
    renew_failures: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProxyOrder:
    uuid: str
    type: Optional[str] = None
    kind: Optional[str] = None
    gb: Optional[float] = None
    quantity: int = 0
    location: Optional[str] = None
    status: Optional[str] = None
    price_cents: Optional[int] = None
    currency: str = "USD"
    proxies: Optional[List[Any]] = None
    auto_extend: bool = False
    extendable: bool = False
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProxyOverview:
    residential: Optional[ResidentialAccess]
    subscription: Optional[ProxySubscription]
    orders: List[ProxyOrder] = field(default_factory=list)


@dataclass
class ResidentialPackage:
    gb: int
    per_gb_cents: Optional[int] = None
    recommended: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResidentialPackagesResponse:
    packages: List[ResidentialPackage] = field(default_factory=list)
    currency: str = "USD"


@dataclass
class StaticPlan:
    id: Optional[int] = None
    name: Optional[str] = None
    price_cents: Optional[int] = None  # null ⇒ price via /quote
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StaticLocation:
    id: Optional[int] = None
    name: Optional[str] = None
    out_of_stock: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StaticProduct:
    id: Optional[int] = None
    type: Optional[str] = None
    name: Optional[str] = None
    plans: List[StaticPlan] = field(default_factory=list)
    locations: List[StaticLocation] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StaticCatalogResponse:
    products: List[StaticProduct] = field(default_factory=list)
    currency: str = "USD"


@dataclass
class ProxyQuote:
    """Public quote — fields vary by ``type``; the full map is on ``.raw``."""

    type: Optional[str] = None
    price_cents: Optional[int] = None
    currency: str = "USD"
    gb: Optional[float] = None
    quantity: Optional[int] = None
    discount_pct: Optional[int] = None
    per_gb_cents: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class Proxies:
    """Wrapper around ``/api/account/proxies/*``."""

    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------ reads --
    def list(self) -> ProxyOverview:
        """Residential connection + subscription + recent orders."""
        d = _unwrap(self._client.request("GET", "/api/account/proxies"))
        residential = d.get("residential")
        subscription = d.get("subscription")
        return ProxyOverview(
            residential=_map_access(residential) if isinstance(residential, dict) else None,
            subscription=_map_subscription(subscription) if isinstance(subscription, dict) else None,
            orders=[_map_order(o) for o in (d.get("orders") or []) if isinstance(o, dict)],
        )

    def packages(self) -> ResidentialPackagesResponse:
        """Residential GB package ladder (price, per-GB, discount)."""
        d = _unwrap(self._client.request("GET", "/api/account/proxies/packages"))
        return ResidentialPackagesResponse(
            packages=[_map_package(p) for p in (d.get("packages") or []) if isinstance(p, dict)],
            currency=str(d.get("currency") or "USD"),
        )

    def catalog(self) -> StaticCatalogResponse:
        """Static (per-IP) catalogue — products / plans / locations."""
        d = _unwrap(self._client.request("GET", "/api/account/proxies/catalog"))
        return StaticCatalogResponse(
            products=[_map_product(p) for p in (d.get("products") or []) if isinstance(p, dict)],
            currency=str(d.get("currency") or "USD"),
        )

    def quote(
        self,
        *,
        type: str = "residential",
        gb: Optional[float] = None,
        subscription: Optional[bool] = None,
        product_id: Optional[int] = None,
        plan_id: Optional[int] = None,
        location_id: Optional[int] = None,
        quantity: Optional[int] = None,
    ) -> ProxyQuote:
        """
        Quote a purchase before buying. Residential/metered: pass ``gb``
        (and optionally ``subscription``). Static: pass ``product_id``,
        ``plan_id``, ``location_id`` and optional ``quantity``.
        """
        params: Dict[str, Any] = {"type": type}
        if gb is not None:
            params["gb"] = gb
        if subscription is not None:
            params["subscription"] = _bool_param(subscription)
        if product_id is not None:
            params["product_id"] = product_id
        if plan_id is not None:
            params["plan_id"] = plan_id
        if location_id is not None:
            params["location_id"] = location_id
        if quantity is not None:
            params["quantity"] = quantity
        d = _unwrap(self._client.request("GET", "/api/account/proxies/quote", params=params))
        return _map_quote(d)

    def locations(self, *, type: str = "residential") -> Dict[str, Any]:
        """
        Available targeting. Residential → ``{type, geo}``; static families →
        ``{type, products}``. Returned as the raw decoded map.
        """
        return _unwrap(self._client.request(
            "GET", "/api/account/proxies/locations", params={"type": type},
        ))

    def usage(self, *, from_: Optional[str] = None, to: Optional[str] = None) -> Dict[str, Any]:
        """Residential usage timeline. Dates are ``YYYY-MM-DD``; both optional."""
        params: Dict[str, Any] = {}
        if from_ is not None:
            params["from"] = from_
        if to is not None:
            params["to"] = to
        return _unwrap(self._client.request("GET", "/api/account/proxies/usage", params=params))

    # ----------------------------------------------------------- writes --
    def purchase(
        self,
        *,
        type: str,
        gb: Optional[float] = None,
        subscription: Optional[bool] = None,
        product_id: Optional[int] = None,
        plan_id: Optional[int] = None,
        location_id: Optional[int] = None,
        location_name: Optional[str] = None,
        quantity: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> ProxyOrder:
        """
        Buy proxies. Residential top-up: ``type="residential"``, ``gb=...``.
        Static IPs: ``type`` in ``isp|datacenter|ipv6|mobile|sneaker`` with
        ``product_id`` / ``plan_id`` / ``location_id`` (+ optional
        ``quantity`` / ``location_name``).
        """
        body: Dict[str, Any] = {"type": type}
        if gb is not None:
            body["gb"] = gb
        if subscription is not None:
            body["subscription"] = subscription
        if product_id is not None:
            body["product_id"] = product_id
        if plan_id is not None:
            body["plan_id"] = plan_id
        if location_id is not None:
            body["location_id"] = location_id
        if location_name is not None:
            body["location_name"] = location_name
        if quantity is not None:
            body["quantity"] = quantity

        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        res = self._client.request(
            "POST", "/api/account/proxies/purchase", json_body=body, headers=headers,
        )
        return _map_order(_unwrap(res))

    def extend(self, order_uuid: str, *, days: Optional[int] = None) -> ProxyOrder:
        """Extend a static (per-IP) order for another period (re-charges its price)."""
        body: Dict[str, Any] = {}
        if days is not None:
            body["days"] = days
        res = self._client.request(
            "POST", f"/api/account/proxies/{_quote(order_uuid)}/extend", json_body=body,
        )
        return _map_order(_unwrap(res))

    def set_auto_renew(self, order_uuid: str, enabled: bool) -> ProxyOrder:
        """Toggle auto-renew (``auto_extend``) on a per-IP order."""
        res = self._client.request(
            "POST",
            f"/api/account/proxies/{_quote(order_uuid)}/auto-renew",
            json_body={"enabled": enabled},
        )
        return _map_order(_unwrap(res))

    # -------------------------------------------- residential subscription --
    def subscription_cancel(self) -> ProxySubscription:
        return self._subscription("cancel")

    def subscription_pause(self) -> ProxySubscription:
        return self._subscription("pause")

    def subscription_resume(self) -> ProxySubscription:
        return self._subscription("resume")

    def _subscription(self, action: str) -> ProxySubscription:
        res = self._client.request("POST", f"/api/account/proxies/subscription/{action}")
        return _map_subscription(_unwrap(res))


# --------------------------------------------------------------- mappers --
def _map_access(d: Dict[str, Any]) -> ResidentialAccess:
    ports_raw = d.get("ports") or {}
    ports = {str(k): _int(v, 0) for k, v in ports_raw.items()} if isinstance(ports_raw, dict) else {}
    return ResidentialAccess(
        host=str(d.get("host") or ""),
        ports=ports,
        username=str(d.get("username") or ""),
        password=str(d.get("password") or ""),
        example=_str_or_none(d.get("example")),
        curl=_str_or_none(d.get("curl")),
        traffic_gb_available=_float(d.get("traffic_gb_available")),
        traffic_gb_used=_float(d.get("traffic_gb_used")),
        raw=dict(d),
    )


def _map_subscription(d: Dict[str, Any]) -> ProxySubscription:
    return ProxySubscription(
        status=str(d.get("status") or ""),
        gb=_float(d.get("gb")),
        discount_pct=_int(d.get("discount_pct"), 0),
        next_renews_at=_str_or_none(d.get("next_renews_at")),
        renew_failures=_int(d.get("renew_failures"), 0),
        raw=dict(d),
    )


def _map_order(d: Dict[str, Any]) -> ProxyOrder:
    gb = d.get("gb")
    proxies = d.get("proxies")
    return ProxyOrder(
        uuid=str(d.get("uuid") or ""),
        type=_str_or_none(d.get("type")),
        kind=_str_or_none(d.get("kind")),
        gb=float(gb) if isinstance(gb, (int, float)) and not isinstance(gb, bool) else None,
        quantity=_int(d.get("quantity"), 0),
        location=_str_or_none(d.get("location")),
        status=_str_or_none(d.get("status")),
        price_cents=_int_or_none(d.get("price_cents")),
        currency=str(d.get("currency") or "USD"),
        proxies=proxies if isinstance(proxies, list) else None,
        auto_extend=bool(d.get("auto_extend")),
        extendable=bool(d.get("extendable")),
        expires_at=_str_or_none(d.get("expires_at")),
        created_at=_str_or_none(d.get("created_at")),
        raw=dict(d),
    )


def _map_package(d: Dict[str, Any]) -> ResidentialPackage:
    return ResidentialPackage(
        gb=_int(d.get("gb"), 0),
        per_gb_cents=_int_or_none(d.get("per_gb_cents")),
        recommended=bool(d.get("recommended")),
        raw=dict(d),
    )


def _map_product(d: Dict[str, Any]) -> StaticProduct:
    plans = [_map_plan(p) for p in (d.get("plans") or []) if isinstance(p, dict)]
    locations = [_map_location(l) for l in (d.get("locations") or []) if isinstance(l, dict)]
    return StaticProduct(
        id=_int_or_none(d.get("id")),
        type=_str_or_none(d.get("type")),
        name=_str_or_none(d.get("name")),
        plans=plans,
        locations=locations,
        raw=dict(d),
    )


def _map_plan(d: Dict[str, Any]) -> StaticPlan:
    return StaticPlan(
        id=_int_or_none(d.get("id")),
        name=_str_or_none(d.get("name")),
        price_cents=_int_or_none(d.get("price_cents")),
        min_quantity=_int_or_none(d.get("min_quantity")),
        max_quantity=_int_or_none(d.get("max_quantity")),
        raw=dict(d),
    )


def _map_location(d: Dict[str, Any]) -> StaticLocation:
    return StaticLocation(
        id=_int_or_none(d.get("id")),
        name=_str_or_none(d.get("name")),
        out_of_stock=bool(d.get("out_of_stock")),
        raw=dict(d),
    )


def _map_quote(d: Dict[str, Any]) -> ProxyQuote:
    gb = d.get("gb")
    return ProxyQuote(
        type=_str_or_none(d.get("type")),
        price_cents=_int_or_none(d.get("price_cents")),
        currency=str(d.get("currency") or "USD"),
        gb=float(gb) if isinstance(gb, (int, float)) and not isinstance(gb, bool) else None,
        quantity=_int_or_none(d.get("quantity")),
        discount_pct=_int_or_none(d.get("discount_pct")),
        per_gb_cents=_int_or_none(d.get("per_gb_cents")),
        raw=dict(d),
    )


# --------------------------------------------------------------- helpers --
def _unwrap(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}


def _str_or_none(v: Any) -> Optional[str]:
    return v if isinstance(v, str) else None


def _int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _int_or_none(v: Any) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _float(v: Any) -> float:
    if isinstance(v, bool):
        return 0.0
    return float(v) if isinstance(v, (int, float)) else 0.0


def _bool_param(v: bool) -> str:
    return "1" if v else "0"


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
