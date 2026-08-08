"""
Marketplace namespace. Browse a normalized, provider-agnostic catalog and buy
digital goods (e.g. accounts). The upstream provider stays invisible; item
attributes are normalized on the wire:

  - ``country``: ISO-3166-1 alpha-2 uppercase, or a region slug
    (``mix``/``cis``/``eu``/``asia``/``africa``/``latam``)
  - ``origin``: ``autoreg`` | ``selfreg`` | ``real`` | ``retrieve``
  - ``format``: ``tdata`` | ``session_json`` | ``session``
  - ``twofa``: bool
  - ``group_by=attributes`` folds SKUs into groups carrying ``prices_cents``

The read-only browse endpoints live under ``/api/public/marketplace/*``; the
authenticated purchase/order endpoints under ``/api/v1/marketplace/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


class Marketplace:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------------ read --
    def catalog(
        self,
        *,
        category: Optional[str] = None,
        country: Optional[str] = None,
        origin: Optional[str] = None,
        format: Optional[str] = None,
        twofa: Optional[bool] = None,
        group_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Browse the normalized catalog. Returns ``items`` (or ``groups`` when grouped)."""
        params: Dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if country is not None:
            params["country"] = country
        if origin is not None:
            params["origin"] = origin
        if format is not None:
            params["format"] = format
        if twofa is not None:
            params["twofa"] = twofa
        if group_by is not None:
            params["group_by"] = group_by
        return self._get("/api/public/marketplace/catalog", params=params or None)

    def categories(self) -> Dict[str, Any]:
        """List the available marketplace categories."""
        return self._get("/api/public/marketplace/categories")

    def filters(self, category: Optional[str] = None) -> Dict[str, Any]:
        """List the filter facets (country/origin/format/twofa) for the catalog."""
        params: Dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        return self._get("/api/public/marketplace/filters", params=params or None)

    # ----------------------------------------------------------------- write --
    def quote(self, category: str, sku: str) -> Dict[str, Any]:
        """Estimate a purchase (price/availability) for a category + SKU before buying."""
        res = self._client.request(
            "POST",
            "/api/v1/marketplace/quote",
            json_body={"category": category, "sku": sku},
        )
        return res if isinstance(res, dict) else {}

    def buy(
        self,
        category: str,
        sku: str,
        quantity: int = 1,
        inputs: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Buy ``quantity`` of a SKU. Returns the created order."""
        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        body: Dict[str, Any] = {"category": category, "sku": sku, "quantity": quantity}
        if inputs is not None:
            body["inputs"] = inputs

        res = self._client.request(
            "POST",
            "/api/v1/marketplace/buy",
            json_body=body,
            headers=headers or None,
        )
        return res if isinstance(res, dict) else {}

    def orders(self) -> Dict[str, Any]:
        """List the caller's marketplace orders."""
        return self._get("/api/v1/marketplace/orders")

    def order(self, uuid: str) -> Dict[str, Any]:
        """Fetch a single marketplace order by UUID."""
        return self._get(f"/api/v1/marketplace/orders/{uuid}")

    def reveal(self, uuid: str) -> Dict[str, Any]:
        """Reveal the delivered goods (credentials / files) for a completed order."""
        res = self._client.request(
            "POST", f"/api/v1/marketplace/orders/{uuid}/reveal"
        )
        return res if isinstance(res, dict) else {}

    # --------------------------------------------------------------- helpers --
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self._client.request("GET", path, params=params)
        return res if isinstance(res, dict) else {}
