"""
Tests for client.web_unblocker.* — list / packages / quote / purchase / subscription.

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


class WebUnblockerListTests(unittest.TestCase):
    def test_list_maps_access_subscription_and_orders(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "access": {
                    "host": "unblock.eveses.com", "port": 12323,
                    "username": "u", "password": "p",
                    "requests_purchased": 10000, "requests_used": 250,
                    "requests_remaining": 9750,
                },
                "subscription": {
                    "status": "active", "requests": 10000, "discount_pct": 5,
                    "next_renews_at": "2026-08-01T00:00:00+00:00", "renew_failures": 0,
                },
                "orders": [
                    {"uuid": "wu1", "product": "web_unblocker", "requests": 10000,
                     "status": "active", "price_cents": 500, "currency": "USD"},
                ],
            }})
        ])
        client = _client(session)
        res = client.web_unblocker.list()

        self.assertEqual(session.calls[0][1], "https://api.example.test/api/account/web-unblocker")
        self.assertEqual(res.access.port, 12323)
        self.assertEqual(res.access.requests_remaining, 9750)
        self.assertEqual(res.subscription.requests, 10000)
        self.assertEqual(len(res.orders), 1)
        self.assertEqual(res.orders[0].uuid, "wu1")


class WebUnblockerQuoteTests(unittest.TestCase):
    def test_quote_sends_requests_param(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "product": "web_unblocker", "requests": 10000, "unit": "request",
                "price_cents": 500, "per_1k_cents": 50, "currency": "USD",
            }})
        ])
        client = _client(session)
        q = client.web_unblocker.quote(requests=10000)

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example.test/api/account/web-unblocker/quote")
        self.assertEqual(kwargs["params"]["requests"], 10000)
        self.assertEqual(q.price_cents, 500)
        self.assertEqual(q.per_1k_cents, 50)


class WebUnblockerPurchaseTests(unittest.TestCase):
    def test_purchase_with_subscription_and_idempotency(self) -> None:
        session = _FakeSession([
            _FakeResponse(201, {"data": {
                "uuid": "wu9", "product": "web_unblocker", "requests": 50000,
                "status": "active", "price_cents": 2000, "currency": "USD",
            }})
        ])
        client = _client(session)
        order = client.web_unblocker.purchase(
            requests=50000, subscription=True, idempotency_key="idem-wu",
        )

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example.test/api/account/web-unblocker/purchase")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "idem-wu")
        self.assertEqual(json.loads(kwargs["data"]), {"requests": 50000, "subscription": True})
        self.assertEqual(order.uuid, "wu9")
        self.assertEqual(order.requests, 50000)


class WebUnblockerSubscriptionTests(unittest.TestCase):
    def test_subscription_pause(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"status": "paused", "requests": 10000, "discount_pct": 5}})
        ])
        client = _client(session)
        sub = client.web_unblocker.subscription_pause()
        self.assertEqual(session.calls[0][0], "POST")
        self.assertEqual(session.calls[0][1],
                         "https://api.example.test/api/account/web-unblocker/subscription/pause")
        self.assertEqual(sub.status, "paused")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
