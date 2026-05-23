"""
Activations / orders namespace.

Note: the public OpenAPI spec exposes orders under `/api/account/orders/*`.
There is no dedicated `/api/v1/activations` route today; for API-key
consumers (kind=api_key Sanctum tokens), v1 is a thin wrapper around the
account-scoped controllers. This module hits the account-scoped paths.
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


class Activations:
    """Wrapper around `/api/account/orders/*`."""

    def __init__(self, client: "Eveses") -> None:
        self._client = client

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
            "/api/account/orders",
            json_body=body,
            headers=headers,
        )
        return _map_order(_unwrap(res))

    def get(self, order_id: str) -> Order:
        res = self._client.request("GET", f"/api/account/orders/{_quote(order_id)}")
        return _map_order(_unwrap(res))

    def cancel(self, order_id: str) -> Order:
        """Release the number and refund the user (where supported)."""
        res = self._client.request("POST", f"/api/account/orders/{_quote(order_id)}/cancel")
        return _map_order(_unwrap(res))

    def finish(self, order_id: str) -> Order:
        """Mark the order completed once the SMS has been consumed."""
        res = self._client.request("POST", f"/api/account/orders/{_quote(order_id)}/finish")
        return _map_order(_unwrap(res))

    def sms(self, order_id: str) -> OrderSmsBundle:
        """
        Get all SMS messages for an order. Combines `stored` (delivered to us
        via webhook) with `fresh` (pulled from the upstream provider on demand).
        """
        res = self._client.request("GET", f"/api/account/orders/{_quote(order_id)}/sms")
        data = _unwrap(res)
        return OrderSmsBundle(
            order_id=str(data.get("order_id") or order_id),
            stored=[_map_sms(m) for m in (data.get("stored") or [])],
            fresh=[_map_sms(m) for m in (data.get("fresh") or [])],
        )


# --------------------------------------------------------------- internals --
def _unwrap(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}


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


def _str_or_none(v: Any) -> Optional[str]:
    return v if isinstance(v, str) else None


def _int_or_none(v: Any) -> Optional[int]:
    return v if isinstance(v, int) else None


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
