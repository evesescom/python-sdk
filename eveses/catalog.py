"""
Catalog namespace — read-only metadata used to drive the UX before
creating an order: which countries / services are available, and how
much each combination costs.

Targets the API-key-authenticated v1 routes:

    GET /api/v1/numbers/countries?mode=
    GET /api/v1/numbers/products?mode=     (the "services" list)
    GET /api/v1/numbers/pricing?mode=&country=&product=&duration=

Wire-shape note: the v1 list endpoint is named `products` for legacy
reasons — it returns the same flat string list the rest of the SDK
calls "services". The pricing endpoint takes `product=` on the wire,
which we accept here under the friendlier `service` name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


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


class Catalog:
    """Wrapper around `/api/v1/numbers/{countries,products,pricing}`."""

    def __init__(self, client: "Eveses") -> None:
        self._client = client

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

    def services(
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
