"""
Numbers namespace — SMS activations/rentals plus the read-only catalog that
drives the order-creation UX. Merges the former ``activations`` and
``catalog`` modules into one surface under ``/api/v1/numbers/*``.

Orders:

    POST   /api/v1/numbers/orders
    GET    /api/v1/numbers/orders/{uuid}
    GET    /api/v1/numbers/orders/{uuid}/sms
    POST   /api/v1/numbers/orders/{uuid}/{cancel,finish,retry,repeat,auto-renew}
    GET    /api/v1/numbers/orders
    GET    /api/v1/numbers/orders/summary
    POST   /api/v1/numbers/orders/batch

Catalog:

    GET    /api/v1/numbers/pricing
    GET    /api/v1/numbers/countries
    GET    /api/v1/numbers/products     (the "services" list)
    GET    /api/v1/numbers/carriers
    GET    /api/v1/numbers/states

Wire-shape note: the v1 list endpoint is named ``products`` for legacy
reasons — it returns the same flat string list the rest of the SDK calls
"services". The pricing endpoint takes ``product=`` on the wire, which we
accept here under the friendlier ``service`` name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


@dataclass
class Order:
    order_id: str
    status: str
    phone: Optional[str] = None
    country: Optional[str] = None
    service: Optional[str] = None
    mode: Optional[str] = None
    price_cents: Optional[int] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderSms:
    id: int
    text: str
    sender: Optional[str] = None
    received_at: Optional[str] = None


@dataclass
class OrderSmsBundle:
    order_id: str
    stored: List[OrderSms]
    fresh: List[OrderSms]


@dataclass
class CatalogCountriesResponse:
    mode: str
    countries: List[str] = field(default_factory=list)


@dataclass
class CatalogServicesResponse:
    mode: str
    services: List[str] = field(default_factory=list)
    country: Optional[str] = None
    currency: Optional[str] = None


@dataclass
class CatalogPricingDuration:
    duration_minutes: int
    price_cents: Optional[int] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    available: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CatalogServiceWithDurations:
    name: str
    durations: List[CatalogPricingDuration] = field(default_factory=list)


@dataclass
class CatalogPricingResponse:
    mode: str
    country: str
    services: List[CatalogServiceWithDurations] = field(default_factory=list)
    currency: Optional[str] = None
    service: Optional[str] = None


class Numbers:
    """Wrapper around ``/api/v1/numbers/*`` (orders + catalog)."""

    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------------ orders --
    def create(
        self,
        *,
        country: str,
        service: str,
        mode: str = "activation",
        duration_minutes: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        max_price_cents: Optional[int] = None,
    ) -> Order:
        """Provision a number for a country/service. Returns the created order."""
        body: Dict[str, Any] = {"mode": mode, "country": country, "service": service}
        if duration_minutes is not None:
            body["duration_minutes"] = duration_minutes
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key
        if max_price_cents is not None:
            body["max_price_cents"] = max_price_cents

        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        res = self._client.request(
            "POST",
            "/api/v1/numbers/orders",
            json_body=body,
            headers=headers or None,
        )
        return _map_order(_unwrap(res))

    def batch(
        self,
        orders: List[Dict[str, Any]],
        *,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        """Create several orders in one call. ``orders`` is a list of order specs."""
        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return self._client.request(
            "POST",
            "/api/v1/numbers/orders/batch",
            json_body={"orders": orders},
            headers=headers or None,
        )

    def get(self, order_id: str) -> Order:
        res = self._client.request("GET", f"/api/v1/numbers/orders/{_quote(order_id)}")
        return _map_order(_unwrap(res))

    def list(
        self,
        *,
        status: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        """List the caller's number orders (paginated, native shape)."""
        params: Dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        return self._client.request(
            "GET", "/api/v1/numbers/orders", params=params or None
        )

    def summary(self) -> Any:
        """Aggregate counts / totals across the caller's number orders."""
        return self._client.request("GET", "/api/v1/numbers/orders/summary")

    def cancel(self, order_id: str) -> Order:
        """Release the number and refund the user (where supported)."""
        res = self._client.request(
            "POST", f"/api/v1/numbers/orders/{_quote(order_id)}/cancel"
        )
        return _map_order(_unwrap(res))

    def finish(self, order_id: str) -> Order:
        """Mark the order completed once the SMS has been consumed."""
        res = self._client.request(
            "POST", f"/api/v1/numbers/orders/{_quote(order_id)}/finish"
        )
        return _map_order(_unwrap(res))

    def retry(self, order_id: str) -> Order:
        """Ask the upstream provider for another SMS on the same number."""
        res = self._client.request(
            "POST", f"/api/v1/numbers/orders/{_quote(order_id)}/retry"
        )
        return _map_order(_unwrap(res))

    def repeat(self, order_id: str, *, idempotency_key: Optional[str] = None) -> Order:
        """Re-order the same country/service as an existing order."""
        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        res = self._client.request(
            "POST",
            f"/api/v1/numbers/orders/{_quote(order_id)}/repeat",
            headers=headers or None,
        )
        return _map_order(_unwrap(res))

    def auto_renew(self, order_id: str, enabled: bool) -> Order:
        """Toggle auto-renew on a rental order."""
        res = self._client.request(
            "POST",
            f"/api/v1/numbers/orders/{_quote(order_id)}/auto-renew",
            json_body={"enabled": enabled},
        )
        return _map_order(_unwrap(res))

    def sms(self, order_id: str) -> OrderSmsBundle:
        """
        Get all SMS messages for an order. Combines `stored` (delivered to us
        via webhook) with `fresh` (pulled from the upstream provider on demand).
        """
        res = self._client.request(
            "GET", f"/api/v1/numbers/orders/{_quote(order_id)}/sms"
        )
        data = _unwrap(res)
        return OrderSmsBundle(
            order_id=str(data.get("order_id") or order_id),
            stored=[_map_sms(m) for m in (data.get("stored") or [])],
            fresh=[_map_sms(m) for m in (data.get("fresh") or [])],
        )

    # ----------------------------------------------------------------- catalog --
    def countries(self, *, mode: str = "activation") -> CatalogCountriesResponse:
        """List ISO-3166-1 alpha-2 country codes that have stock for ``mode``."""
        res = self._client.request(
            "GET",
            "/api/v1/numbers/countries",
            params={"mode": mode},
        )
        d = _unwrap(res)
        countries_raw = d.get("countries") or []
        countries = [str(c) for c in countries_raw] if isinstance(countries_raw, list) else []
        return CatalogCountriesResponse(
            mode=str(d.get("mode") or mode),
            countries=countries,
        )

    def products(
        self,
        *,
        mode: str = "activation",
        country: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> CatalogServicesResponse:
        """
        List service / product codes available globally for ``mode``.

        ``country`` and ``currency`` are accepted for symmetry with the
        broader catalog API but are currently informational on the v1
        endpoint, which returns the unified product list.
        """
        res = self._client.request(
            "GET",
            "/api/v1/numbers/products",
            params={"mode": mode},
        )
        d = _unwrap(res)
        products_raw = d.get("products") or []
        services = [str(p) for p in products_raw] if isinstance(products_raw, list) else []
        return CatalogServicesResponse(
            mode=str(d.get("mode") or mode),
            services=services,
            country=country.lower() if isinstance(country, str) and country else None,
            currency=currency.upper() if isinstance(currency, str) and currency else None,
        )

    # Backwards-friendly alias: the product list is what callers call "services".
    services = products

    def carriers(
        self, *, country: str, mode: str = "activation"
    ) -> Dict[str, Any]:
        """List carriers/operators available for a country/mode."""
        return _dict(
            self._client.request(
                "GET",
                "/api/v1/numbers/carriers",
                params={"mode": mode, "country": country.lower()},
            )
        )

    def states(self, *, country: str, mode: str = "activation") -> Dict[str, Any]:
        """List states/regions available for a country/mode (where supported)."""
        return _dict(
            self._client.request(
                "GET",
                "/api/v1/numbers/states",
                params={"mode": mode, "country": country.lower()},
            )
        )

    def pricing(
        self,
        *,
        country: str,
        service: str,
        mode: str = "activation",
        currency: Optional[str] = None,
        duration_minutes: Optional[int] = None,
    ) -> CatalogPricingResponse:
        """Fetch pricing for a country/service pair (optionally for a specific duration)."""
        if not country:
            raise ValueError("country is required")
        if not service:
            raise ValueError("service is required")

        params: Dict[str, Any] = {
            "mode": mode,
            "country": country.lower(),
            "product": service,
        }
        if currency:
            params["currency"] = currency.upper()
        if duration_minutes is not None:
            params["duration"] = duration_minutes

        res = self._client.request(
            "GET",
            "/api/v1/numbers/pricing",
            params=params,
        )
        d = _unwrap(res)

        services_raw = d.get("services") or []
        services: List[CatalogServiceWithDurations] = []
        if isinstance(services_raw, list):
            for entry in services_raw:
                services.append(_map_service_entry(entry))

        return CatalogPricingResponse(
            mode=str(d.get("mode") or mode),
            country=str(d.get("country") or country.lower()),
            currency=_str_or_none(d.get("currency")) or (currency.upper() if currency else None),
            service=service,
            services=services,
        )


# --------------------------------------------------------------- internals --
def _unwrap(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}


def _dict(payload: Any) -> Dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _map_order(d: Dict[str, Any]) -> Order:
    return Order(
        order_id=str(d.get("order_id") or ""),
        status=str(d.get("status") or "pending"),
        phone=_str_or_none(d.get("phone")),
        country=_str_or_none(d.get("country")),
        service=_str_or_none(d.get("service")),
        mode=_str_or_none(d.get("mode")),
        price_cents=_int_or_none(d.get("price_cents")),
        expires_at=_str_or_none(d.get("expires_at")),
        created_at=_str_or_none(d.get("created_at")),
        raw=dict(d),
    )


def _map_sms(m: Dict[str, Any]) -> OrderSms:
    return OrderSms(
        id=int(m.get("id") or 0),
        text=str(m.get("text") or ""),
        sender=_str_or_none(m.get("sender")),
        received_at=_str_or_none(m.get("received_at")),
    )


def _map_service_entry(entry: Any) -> CatalogServiceWithDurations:
    if not isinstance(entry, dict):
        return CatalogServiceWithDurations(name="", durations=[])
    durations_raw = entry.get("durations") or []
    durations: List[CatalogPricingDuration] = []
    if isinstance(durations_raw, list):
        for d in durations_raw:
            durations.append(_map_duration(d))
    return CatalogServiceWithDurations(
        name=str(entry.get("name") or ""),
        durations=durations,
    )


def _map_duration(d: Any) -> CatalogPricingDuration:
    if not isinstance(d, dict):
        return CatalogPricingDuration(duration_minutes=0)
    available = d.get("available")
    if not isinstance(available, bool):
        in_stock = d.get("in_stock")
        available = in_stock if isinstance(in_stock, bool) else None
    return CatalogPricingDuration(
        duration_minutes=int(d.get("duration_minutes") or 0),
        price_cents=_int_or_none(d.get("price_cents")),
        price=_float_or_none(d.get("price")),
        currency=_str_or_none(d.get("currency")),
        available=available,
        raw=dict(d),
    )


def _str_or_none(v: Any) -> Optional[str]:
    return v if isinstance(v, str) else None


def _int_or_none(v: Any) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _float_or_none(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
