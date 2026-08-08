"""
Tests for the marketplace module and the proxy per-country geo drill-down.
Uses a fake session (no network); asserts method / url / body / params /
headers on the wire.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Dict, List, Optional, Tuple

from eveses import Eveses, Marketplace


class _FakeResponse:
    def __init__(self, status_code: int, body: Any = None, headers: Optional[Dict[str, str]] = None) -> None:
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


class MarketplaceTests(unittest.TestCase):
    def _client(self, responses: List[_FakeResponse]) -> Tuple[Eveses, _FakeSession]:
        session = _FakeSession(responses)
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        return client, session

    def test_registered_on_client(self) -> None:
        client, _ = self._client([])
        self.assertIsInstance(client.marketplace, Marketplace)

    def test_catalog_sends_only_provided_params(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"items": []}),
        ])
        client.marketplace.catalog(category="accounts", country="US", twofa=True, group_by="attributes")

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://x.test/api/public/marketplace/catalog")
        self.assertEqual(
            kwargs["params"],
            {"category": "accounts", "country": "US", "twofa": True, "group_by": "attributes"},
        )

    def test_catalog_no_params(self) -> None:
        client, session = self._client([_FakeResponse(200, {"items": []})])
        client.marketplace.catalog()
        self.assertIsNone(session.calls[0][2]["params"])

    def test_categories_and_filters(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"categories": ["accounts"]}),
            _FakeResponse(200, {"country": []}),
        ])
        client.marketplace.categories()
        self.assertEqual(session.calls[0][1], "https://x.test/api/public/marketplace/categories")
        self.assertIsNone(session.calls[0][2]["params"])

        client.marketplace.filters(category="accounts")
        self.assertEqual(session.calls[1][1], "https://x.test/api/public/marketplace/filters")
        self.assertEqual(session.calls[1][2]["params"], {"category": "accounts"})

    def test_quote_posts_body(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"price_cents": 500}),
        ])
        out = client.marketplace.quote("accounts", "acc_telegram_us")
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://x.test/api/v1/marketplace/quote")
        self.assertEqual(json.loads(kwargs["data"]), {"category": "accounts", "sku": "acc_telegram_us"})
        self.assertEqual(out["price_cents"], 500)

    def test_buy_sends_body_and_idempotency_key(self) -> None:
        client, session = self._client([
            _FakeResponse(201, {"uuid": "mp_1", "status": "pending"}),
        ])
        client.marketplace.buy(
            "accounts", "acc_x", quantity=3, inputs={"note": "hi"}, idempotency_key="idem-mp"
        )
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://x.test/api/v1/marketplace/buy")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "idem-mp")
        self.assertEqual(
            json.loads(kwargs["data"]),
            {"category": "accounts", "sku": "acc_x", "quantity": 3, "inputs": {"note": "hi"}},
        )

    def test_buy_omits_inputs_when_absent(self) -> None:
        client, session = self._client([_FakeResponse(201, {"uuid": "mp_1"})])
        client.marketplace.buy("accounts", "acc_x")
        sent = json.loads(session.calls[0][2]["data"])
        self.assertEqual(sent, {"category": "accounts", "sku": "acc_x", "quantity": 1})
        self.assertNotIn("Idempotency-Key", session.calls[0][2].get("headers") or {})

    def test_orders_order_reveal_routes(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"orders": []}),
            _FakeResponse(200, {"uuid": "mp_1"}),
            _FakeResponse(200, {"credentials": "…"}),
        ])
        client.marketplace.orders()
        self.assertEqual(session.calls[0][0], "GET")
        self.assertEqual(session.calls[0][1], "https://x.test/api/v1/marketplace/orders")

        client.marketplace.order("mp_1")
        self.assertEqual(session.calls[1][1], "https://x.test/api/v1/marketplace/orders/mp_1")

        client.marketplace.reveal("mp_1")
        self.assertEqual(session.calls[2][0], "POST")
        self.assertEqual(session.calls[2][1], "https://x.test/api/v1/marketplace/orders/mp_1/reveal")


class ProxyLocationsDetailTests(unittest.TestCase):
    def _client(self, responses: List[_FakeResponse]) -> Tuple[Eveses, _FakeSession]:
        session = _FakeSession(responses)
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        return client, session

    def test_locations_detail_builds_params(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"type": "residential", "country": "US", "geo": {}}),
        ])
        out = client.proxy.locations_detail("US")
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://x.test/api/v1/proxy/locations/detail")
        self.assertEqual(kwargs["params"], {"type": "residential", "country": "US"})
        self.assertEqual(out["country"], "US")


if __name__ == "__main__":
    unittest.main()
