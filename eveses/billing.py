"""
Billing namespace. Hits `/api/v1/billing`.

Two documents share the word "invoice" and read in opposite directions, so
they are two methods rather than one with a flag:

* :meth:`Billing.issue_invoice` asks the customer to pay. It mints a payment
  reference and a due date.
* :meth:`Billing.invoice_for_deposit` documents a top-up that already settled.
  It comes back marked paid, with no due date and nothing to act on.

Handing somebody the first when they wanted the second reads as an attempt to
charge them twice.

Nothing can be issued until :meth:`Billing.save_profile` has run — the details
are frozen onto each document at issue time, so editing the profile later never
rewrites a document already in somebody's books.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


@dataclass
class BillingProfile:
    kind: str
    legal_name: str
    country: str
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    tax_id: Optional[str] = None
    vat_number: Optional[str] = None
    email_for_invoices: Optional[str] = None


@dataclass
class InvoiceLine:
    description: str
    quantity: int
    unit_price_cents: int
    amount_cents: int


@dataclass
class Invoice:
    uuid: str
    number: str
    status: str
    amount_cents: int
    total_cents: int
    currency: str
    issued_at: Optional[str] = None
    #: ``None`` on a receipt: nothing is due on money already received.
    due_at: Optional[str] = None
    paid_at: Optional[str] = None
    payment_reference: Optional[str] = None
    bill_to: Dict[str, Any] = field(default_factory=dict)
    seller: Dict[str, Any] = field(default_factory=dict)
    lines: List[InvoiceLine] = field(default_factory=list)

    @property
    def is_paid(self) -> bool:
        return self.status == "paid"


class Billing:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    # ------------------------------------------------------------------ profile

    def profile(self) -> Optional[BillingProfile]:
        """Who we bill. ``None`` when nothing has been set yet."""
        d = _unwrap(self._client.request("GET", "/api/v1/billing/profile"))
        if not d.get("legal_name"):
            return None
        return _to_profile(d)

    def save_profile(self, **fields: Any) -> BillingProfile:
        """
        Set or update the invoicing details. Do it once.

        Only the fields you pass are changed, so correcting a postcode does not
        blank a tax number you did not mention.
        """
        payload = {k: v for k, v in fields.items() if v is not None}
        d = _unwrap(self._client.request("PUT", "/api/v1/billing/profile", json_body=payload))
        return _to_profile(d)

    # ----------------------------------------------------------------- invoices

    def invoices(self) -> List[Invoice]:
        """Invoices issued to this account, newest first."""
        d = _unwrap(self._client.request("GET", "/api/v1/billing/invoices"))
        rows = d.get("invoices") if isinstance(d.get("invoices"), list) else []
        return [_to_invoice(r) for r in rows]

    def invoice(self, uuid: str) -> Invoice:
        """One invoice in full, including the frozen seller and bill-to."""
        return _to_invoice(_unwrap(self._client.request("GET", f"/api/v1/billing/invoices/{uuid}")))

    def issue_invoice(
        self,
        amount_cents: int,
        currency: str = "USD",
        note: Optional[str] = None,
    ) -> Invoice:
        """
        An invoice to PAY, for money you are about to send. $10 to $10,000.

        You get a payment reference; quote it when paying and the amount lands
        on your balance.
        """
        payload: Dict[str, Any] = {
            "amount_cents": amount_cents,
            "currency": currency,
            "purpose": "wallet_topup",
        }
        if note is not None:
            payload["note"] = note
        return _to_invoice(_unwrap(self._client.request("POST", "/api/v1/billing/invoices", json_body=payload)))

    def invoice_for_deposit(self, deposit_uuid: str) -> Invoice:
        """
        A receipt for a top-up that already settled.

        Comes back marked paid, with no due date. Shows what actually left your
        account — a $10.00 top-up charged at $10.20 is invoiced as $10.20 with
        the card fee itemised, so it reconciles against a card statement rather
        than against your balance.

        Idempotent: asking twice returns the same document, not a second
        invoice number for one payment.
        """
        return _to_invoice(
            _unwrap(self._client.request("POST", f"/api/v1/billing/deposits/{deposit_uuid}/invoice"))
        )

    def cancel_invoice(self, uuid: str) -> Invoice:
        """
        Cancel an unpaid invoice.

        The number stays with it — freeing one for reuse is the gap an audit
        asks about.
        """
        return _to_invoice(_unwrap(self._client.request("POST", f"/api/v1/billing/invoices/{uuid}/cancel")))

    def invoice_pdf(self, uuid: str) -> bytes:
        """The invoice as a PDF, ready to file."""
        return self._client.request(
            "GET",
            f"/api/v1/billing/invoices/{uuid}/pdf",
            headers={"Accept": "application/pdf"},
            raw=True,
        )


# --------------------------------------------------------------------- helpers


def _unwrap(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_profile(d: Dict[str, Any]) -> BillingProfile:
    return BillingProfile(
        kind=str(d.get("kind") or "business"),
        legal_name=str(d.get("legal_name") or ""),
        country=str(d.get("country") or ""),
        address_line1=d.get("address_line1"),
        address_line2=d.get("address_line2"),
        city=d.get("city"),
        postal_code=d.get("postal_code"),
        tax_id=d.get("tax_id"),
        vat_number=d.get("vat_number"),
        email_for_invoices=d.get("email_for_invoices"),
    )


def _to_invoice(d: Dict[str, Any]) -> Invoice:
    lines = []
    for raw in d.get("lines") or []:
        if not isinstance(raw, dict):
            continue
        lines.append(
            InvoiceLine(
                description=str(raw.get("description") or ""),
                quantity=_int(raw.get("quantity"), 1),
                unit_price_cents=_int(raw.get("unit_price_cents"), _int(raw.get("amount_cents"))),
                amount_cents=_int(raw.get("amount_cents")),
            )
        )

    tax = d.get("tax") if isinstance(d.get("tax"), dict) else {}

    return Invoice(
        uuid=str(d.get("uuid") or ""),
        number=str(d.get("number") or ""),
        status=str(d.get("status") or ""),
        amount_cents=_int(d.get("amount_cents")),
        total_cents=_int(d.get("total_cents"), _int(d.get("amount_cents")) + _int(tax.get("amount_cents"))),
        currency=str(d.get("currency") or "USD"),
        issued_at=d.get("issued_at"),
        due_at=d.get("due_at"),
        paid_at=d.get("paid_at"),
        payment_reference=(d.get("payment") or {}).get("reference") if isinstance(d.get("payment"), dict) else d.get("payment_reference"),
        bill_to=d.get("bill_to") if isinstance(d.get("bill_to"), dict) else {},
        seller=d.get("seller") if isinstance(d.get("seller"), dict) else {},
        lines=lines,
    )
