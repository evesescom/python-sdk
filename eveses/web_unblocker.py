"""
Web Unblocker namespace — an anti-bot scraping endpoint billed per successful
request. Separate product from proxies. Hits ``/api/account/web-unblocker/*``.

The provider stays invisible: the connection is returned under the white-label
host. Money is always integer cents; ``currency`` is ``"USD"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


# ---------------------------------------------------------------- models --
@dataclass
class WebUnblockerAccess:
    host: str
    port: int
    username: str
    password: str
    example: Optional[str] = None
    curl: Optional[str] = None
    requests_purchased: int = 0
    requests_used: int = 0
    requests_remaining: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebUnblockerOrder:
    uuid: str
    product: str = "web_unblocker"
    requests: int = 0
    status: Optional[str] = None
    price_cents: Optional[int] = None
    currency: str = "USD"
    created_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebUnblockerSubscription:
    status: str
    requests: int = 0
    discount_pct: int = 0
    next_renews_at: Optional[str] = None
    renew_failures: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebUnblockerOverview:
    access: Optional[WebUnblockerAccess]
    subscription: Optional[WebUnblockerSubscription]
    orders: List[WebUnblockerOrder] = field(default_factory=list)


@dataclass
class WebUnblockerPackage:
    requests: int
    per_1k_cents: Optional[int] = None
    total_cents: Optional[int] = None
    base_per_1k_cents: Optional[int] = None
    discount_pct: int = 0
    recommended: bool = False
    currency: str = "USD"
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebUnblockerPackagesResponse:
    packages: List[WebUnblockerPackage] = field(default_factory=list)
    currency: str = "USD"


@dataclass
class WebUnblockerQuote:
    product: str = "web_unblocker"
    requests: int = 0
    unit: str = "request"
    price_cents: Optional[int] = None
    per_1k_cents: Optional[int] = None
    currency: str = "USD"
    raw: Dict[str, Any] = field(default_factory=dict)


class WebUnblocker:
    """Wrapper around ``/api/account/web-unblocker/*``."""

    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------ reads --
    def list(self) -> WebUnblockerOverview:
        """Connection credentials + quota + order history."""
        d = _unwrap(self._client.request("GET", "/api/account/web-unblocker"))
        access = d.get("access")
        subscription = d.get("subscription")
        return WebUnblockerOverview(
            access=_map_access(access) if isinstance(access, dict) else None,
            subscription=_map_subscription(subscription) if isinstance(subscription, dict) else None,
            orders=[_map_order(o) for o in (d.get("orders") or []) if isinstance(o, dict)],
        )

    def packages(self) -> WebUnblockerPackagesResponse:
        """Request-bundle ladder (price, per-1k rate, discount)."""
        d = _unwrap(self._client.request("GET", "/api/account/web-unblocker/packages"))
        return WebUnblockerPackagesResponse(
            packages=[_map_package(p) for p in (d.get("packages") or []) if isinstance(p, dict)],
            currency=str(d.get("currency") or "USD"),
        )

    def quote(self, *, requests: int, subscription: Optional[bool] = None) -> WebUnblockerQuote:
        """Quote a purchase before buying (custom amounts allowed)."""
        params: Dict[str, Any] = {"requests": requests}
        if subscription is not None:
            params["subscription"] = "1" if subscription else "0"
        d = _unwrap(self._client.request(
            "GET", "/api/account/web-unblocker/quote", params=params,
        ))
        return _map_quote(d)

    # ----------------------------------------------------------- writes --
    def purchase(
        self,
        *,
        requests: int,
        subscription: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
    ) -> WebUnblockerOrder:
        """Buy a request bundle (top up the user's pool)."""
        body: Dict[str, Any] = {"requests": requests}
        if subscription is not None:
            body["subscription"] = subscription

        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        res = self._client.request(
            "POST", "/api/account/web-unblocker/purchase", json_body=body, headers=headers,
        )
        return _map_order(_unwrap(res))

    # -------------------------------------------------------- subscription --
    def subscription_cancel(self) -> WebUnblockerSubscription:
        return self._subscription("cancel")

    def subscription_pause(self) -> WebUnblockerSubscription:
        return self._subscription("pause")

    def subscription_resume(self) -> WebUnblockerSubscription:
        return self._subscription("resume")

    def _subscription(self, action: str) -> WebUnblockerSubscription:
        res = self._client.request("POST", f"/api/account/web-unblocker/subscription/{action}")
        return _map_subscription(_unwrap(res))


# --------------------------------------------------------------- mappers --
def _map_access(d: Dict[str, Any]) -> WebUnblockerAccess:
    return WebUnblockerAccess(
        host=str(d.get("host") or ""),
        port=_int(d.get("port"), 0),
        username=str(d.get("username") or ""),
        password=str(d.get("password") or ""),
        example=_str_or_none(d.get("example")),
        curl=_str_or_none(d.get("curl")),
        requests_purchased=_int(d.get("requests_purchased"), 0),
        requests_used=_int(d.get("requests_used"), 0),
        requests_remaining=_int(d.get("requests_remaining"), 0),
        raw=dict(d),
    )


def _map_order(d: Dict[str, Any]) -> WebUnblockerOrder:
    return WebUnblockerOrder(
        uuid=str(d.get("uuid") or ""),
        product=str(d.get("product") or "web_unblocker"),
        requests=_int(d.get("requests"), 0),
        status=_str_or_none(d.get("status")),
        price_cents=_int_or_none(d.get("price_cents")),
        currency=str(d.get("currency") or "USD"),
        created_at=_str_or_none(d.get("created_at")),
        raw=dict(d),
    )


def _map_subscription(d: Dict[str, Any]) -> WebUnblockerSubscription:
    return WebUnblockerSubscription(
        status=str(d.get("status") or ""),
        requests=_int(d.get("requests"), 0),
        discount_pct=_int(d.get("discount_pct"), 0),
        next_renews_at=_str_or_none(d.get("next_renews_at")),
        renew_failures=_int(d.get("renew_failures"), 0),
        raw=dict(d),
    )


def _map_package(d: Dict[str, Any]) -> WebUnblockerPackage:
    return WebUnblockerPackage(
        requests=_int(d.get("requests"), 0),
        per_1k_cents=_int_or_none(d.get("per_1k_cents")),
        total_cents=_int_or_none(d.get("total_cents")),
        base_per_1k_cents=_int_or_none(d.get("base_per_1k_cents")),
        discount_pct=_int(d.get("discount_pct"), 0),
        recommended=bool(d.get("recommended")),
        currency=str(d.get("currency") or "USD"),
        raw=dict(d),
    )


def _map_quote(d: Dict[str, Any]) -> WebUnblockerQuote:
    return WebUnblockerQuote(
        product=str(d.get("product") or "web_unblocker"),
        requests=_int(d.get("requests"), 0),
        unit=str(d.get("unit") or "request"),
        price_cents=_int_or_none(d.get("price_cents")),
        per_1k_cents=_int_or_none(d.get("per_1k_cents")),
        currency=str(d.get("currency") or "USD"),
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
