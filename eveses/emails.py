"""
Emails namespace — rent an inbox address (our own catch-all domains, or a
reseller) and read its mail. Hits ``/api/account/emails/*``.

The provider stays invisible. Fetching a single address (:meth:`Emails.get`)
also live-syncs reseller inboxes — it is the inbox-refresh mechanism, so poll
it to receive new mail. Money is always integer cents; ``currency`` is ``"USD"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


# ---------------------------------------------------------------- models --
@dataclass
class EmailMessage:
    id: Optional[str] = None
    from_: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None  # may be plain text or HTML
    received_at: Optional[str] = None
    read_at: Optional[str] = None
    is_read: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailMessagesPage:
    """A page of inbox messages with cursor-free pagination metadata."""

    messages: List[EmailMessage] = field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    has_more: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailAddress:
    uuid: str
    address: Optional[str] = None
    domain: Optional[str] = None
    site: Optional[str] = None
    status: Optional[str] = None
    price_cents: Optional[int] = None
    currency: str = "USD"
    message_count: int = 0
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    messages: List[EmailMessage] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailDomain:
    provider: Optional[str] = None
    domain: Optional[str] = None
    price_cents: Optional[int] = None
    available: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailDomainsResponse:
    domains: List[EmailDomain] = field(default_factory=list)
    currency: str = "USD"


@dataclass
class EmailQuote:
    domain: Optional[str] = None
    provider: Optional[str] = None
    price_cents: Optional[int] = None
    currency: str = "USD"
    raw: Dict[str, Any] = field(default_factory=dict)


class Emails:
    """Wrapper around ``/api/account/emails/*``."""

    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------ reads --
    def list(self, *, include_released: bool = False) -> List[EmailAddress]:
        """
        The user's rented addresses. Pass ``include_released=True`` to also
        return released (cancelled) addresses.
        """
        params: Dict[str, Any] = {}
        if include_released:
            params["include_released"] = "1"
        d = _unwrap(self._client.request("GET", "/api/account/emails", params=params))
        return [_map_address(e) for e in (d.get("emails") or []) if isinstance(e, dict)]

    def domains(self, *, site: Optional[str] = None) -> EmailDomainsResponse:
        """
        Rentable domains (our price). Pass ``site`` for reseller providers;
        our catch-all domains ignore it.
        """
        params: Dict[str, Any] = {}
        if site is not None:
            params["site"] = site
        d = _unwrap(self._client.request("GET", "/api/account/emails/domains", params=params))
        return EmailDomainsResponse(
            domains=[_map_domain(x) for x in (d.get("domains") or []) if isinstance(x, dict)],
            currency=str(d.get("currency") or "USD"),
        )

    def quote(
        self,
        *,
        domain: str,
        site: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> EmailQuote:
        """Price a concrete pick."""
        params: Dict[str, Any] = {"domain": domain}
        if site is not None:
            params["site"] = site
        if provider is not None:
            params["provider"] = provider
        d = _unwrap(self._client.request("GET", "/api/account/emails/quote", params=params))
        return _map_quote(d)

    def get(self, uuid: str) -> EmailAddress:
        """
        One address + its received messages. This call also live-syncs
        reseller inboxes from the upstream provider — poll it for new mail.
        """
        res = self._client.request("GET", f"/api/account/emails/{_quote(uuid)}")
        return _map_address(_unwrap(res))

    def messages(self, uuid: str, *, page: int = 1, per_page: int = 20) -> EmailMessagesPage:
        """A paginated page of an address's received messages."""
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        d = _unwrap(self._client.request(
            "GET", f"/api/account/emails/{_quote(uuid)}/messages", params=params,
        ))
        return _map_messages_page(d)

    # ----------------------------------------------------------- writes --
    def purchase(
        self,
        *,
        domain: str,
        site: Optional[str] = None,
        provider: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> EmailAddress:
        """Rent an address."""
        body: Dict[str, Any] = {"domain": domain}
        if site is not None:
            body["site"] = site
        if provider is not None:
            body["provider"] = provider

        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        res = self._client.request(
            "POST", "/api/account/emails/purchase", json_body=body, headers=headers,
        )
        return _map_address(_unwrap(res))

    def mark_read(self, uuid: str, message_id: str) -> Dict[str, Any]:
        """
        Mark one message as read. Returns the raw decoded map
        (``{"id": "<message_id>", "read": true}``).
        """
        res = self._client.request(
            "POST",
            f"/api/account/emails/{_quote(uuid)}/messages/{_quote(message_id)}/read",
        )
        return _unwrap(res)

    def delete(self, uuid: str) -> EmailAddress:
        """
        Release an address (soft cancel, no refund). Returns the address with
        ``status="cancelled"``.
        """
        res = self._client.request("DELETE", f"/api/account/emails/{_quote(uuid)}")
        return _map_address(_unwrap(res))


# --------------------------------------------------------------- mappers --
def _map_address(d: Dict[str, Any]) -> EmailAddress:
    messages_raw = d.get("messages")
    messages = (
        [_map_message(m) for m in messages_raw if isinstance(m, dict)]
        if isinstance(messages_raw, list)
        else []
    )
    return EmailAddress(
        uuid=str(d.get("uuid") or ""),
        address=_str_or_none(d.get("address")),
        domain=_str_or_none(d.get("domain")),
        site=_str_or_none(d.get("site")),
        status=_str_or_none(d.get("status")),
        price_cents=_int_or_none(d.get("price_cents")),
        currency=str(d.get("currency") or "USD"),
        message_count=_int(d.get("message_count"), 0),
        expires_at=_str_or_none(d.get("expires_at")),
        created_at=_str_or_none(d.get("created_at")),
        messages=messages,
        raw=dict(d),
    )


def _map_message(d: Dict[str, Any]) -> EmailMessage:
    mid = d.get("id")
    return EmailMessage(
        id=str(mid) if mid is not None else None,
        from_=_str_or_none(d.get("from")),
        subject=_str_or_none(d.get("subject")),
        body=_str_or_none(d.get("body")),
        received_at=_str_or_none(d.get("received_at")),
        read_at=_str_or_none(d.get("read_at")),
        is_read=bool(d.get("is_read")),
        raw=dict(d),
    )


def _map_messages_page(d: Dict[str, Any]) -> EmailMessagesPage:
    messages_raw = d.get("messages")
    messages = (
        [_map_message(m) for m in messages_raw if isinstance(m, dict)]
        if isinstance(messages_raw, list)
        else []
    )
    return EmailMessagesPage(
        messages=messages,
        page=_int(d.get("page"), 1),
        per_page=_int(d.get("per_page"), 20),
        total=_int(d.get("total"), 0),
        has_more=bool(d.get("has_more")),
        raw=dict(d),
    )


def _map_domain(d: Dict[str, Any]) -> EmailDomain:
    return EmailDomain(
        provider=_str_or_none(d.get("provider")),
        domain=_str_or_none(d.get("domain")),
        price_cents=_int_or_none(d.get("price_cents")),
        available=bool(d.get("available")),
        raw=dict(d),
    )


def _map_quote(d: Dict[str, Any]) -> EmailQuote:
    return EmailQuote(
        domain=_str_or_none(d.get("domain")),
        provider=_str_or_none(d.get("provider")),
        price_cents=_int_or_none(d.get("price_cents")),
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


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
