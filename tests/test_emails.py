"""
Tests for client.emails.* — list / domains / quote / purchase / get / delete.

Same fake-session style as test_client.py; never touches the network.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Dict, List, Optional, Tuple

from eveses import Eveses


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.reason = "OK" if 200 <= status_code < 300 else "Error"
        self.text = "" if body is None else json.dumps(body)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no body")
        return self._body


class _FakeSession:
    def __init__(self, responses: List[_FakeResponse]) -> None:
        self._queue = list(responses)
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append((method, url, kwargs))
        if not self._queue:
            raise AssertionError("FakeSession: no more responses queued")
        return self._queue.pop(0)


def _client(session: _FakeSession) -> Eveses:
    return Eveses(api_key="k", base_url="https://api.example.test", session=session)


class EmailListTests(unittest.TestCase):
    def test_list_maps_addresses(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"emails": [
                {"uuid": "e1", "address": "abc@evs.io", "domain": "evs.io",
                 "site": None, "status": "active", "price_cents": 100,
                 "currency": "USD", "message_count": 0},
            ]}})
        ])
        client = _client(session)
        res = client.emails.list()
        self.assertEqual(session.calls[0][1], "https://api.example.test/api/account/emails")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].uuid, "e1")
        self.assertEqual(res[0].address, "abc@evs.io")


class EmailDomainsTests(unittest.TestCase):
    def test_domains_passes_site(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "domains": [{"provider": "hero", "domain": "evs.io",
                             "price_cents": 100, "available": True}],
                "currency": "USD",
            }})
        ])
        client = _client(session)
        res = client.emails.domains(site="facebook.com")
        self.assertEqual(session.calls[0][2]["params"], {"site": "facebook.com"})
        self.assertEqual(res.domains[0].provider, "hero")
        self.assertTrue(res.domains[0].available)


class EmailQuoteTests(unittest.TestCase):
    def test_quote(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "domain": "evs.io", "provider": "hero", "price_cents": 100, "currency": "USD",
            }})
        ])
        client = _client(session)
        q = client.emails.quote(domain="evs.io", site="facebook.com", provider="hero")
        params = session.calls[0][2]["params"]
        self.assertEqual(params, {"domain": "evs.io", "site": "facebook.com", "provider": "hero"})
        self.assertEqual(q.price_cents, 100)


class EmailPurchaseTests(unittest.TestCase):
    def test_purchase_with_idempotency(self) -> None:
        session = _FakeSession([
            _FakeResponse(201, {"data": {
                "uuid": "e9", "address": "xyz@evs.io", "domain": "evs.io",
                "status": "active", "price_cents": 100, "currency": "USD",
                "message_count": 0,
            }})
        ])
        client = _client(session)
        order = client.emails.purchase(domain="evs.io", idempotency_key="idem-e")

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example.test/api/account/emails/purchase")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "idem-e")
        self.assertEqual(json.loads(kwargs["data"]), {"domain": "evs.io"})
        self.assertEqual(order.uuid, "e9")


class EmailInboxTests(unittest.TestCase):
    def test_get_maps_messages(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "uuid": "e1", "address": "abc@evs.io", "domain": "evs.io",
                "status": "received", "price_cents": 100, "currency": "USD",
                "message_count": 1,
                "messages": [
                    {"from": "noreply@x.com", "subject": "Code: 12345",
                     "body": "<b>12345</b>", "received_at": "2026-07-01T10:00:00+00:00"},
                ],
            }})
        ])
        client = _client(session)
        addr = client.emails.get("e1")

        self.assertEqual(session.calls[0][0], "GET")
        self.assertEqual(session.calls[0][1], "https://api.example.test/api/account/emails/e1")
        self.assertEqual(len(addr.messages), 1)
        self.assertEqual(addr.messages[0].from_, "noreply@x.com")
        self.assertEqual(addr.messages[0].subject, "Code: 12345")

    def test_delete_soft_cancels(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"uuid": "e1", "address": "abc@evs.io",
                                         "status": "cancelled", "price_cents": 100}})
        ])
        client = _client(session)
        addr = client.emails.delete("e1")
        self.assertEqual(session.calls[0][0], "DELETE")
        self.assertEqual(session.calls[0][1], "https://api.example.test/api/account/emails/e1")
        self.assertEqual(addr.status, "cancelled")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
