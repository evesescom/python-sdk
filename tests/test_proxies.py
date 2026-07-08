"""
Tests for client.proxies.* — list / packages / quote / purchase / management.

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


class ProxyListTests(unittest.TestCase):
    def test_list_maps_residential_subscription_and_orders(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "residential": {
                    "host": "proxy.eveses.com",
                    "ports": {"http": 12321, "socks5": 32325},
                    "username": "u1", "password": "p1",
                    "traffic_gb_available": 4.5, "traffic_gb_used": 0.5,
                },
                "subscription": {
                    "status": "active", "gb": 5.0, "discount_pct": 10,
                    "next_renews_at": "2026-08-01T00:00:00+00:00", "renew_failures": 0,
                },
                "orders": [
                    {"uuid": "o1", "type": "isp", "kind": "static", "quantity": 2,
                     "status": "active", "price_cents": 900, "currency": "USD",
                     "auto_extend": True, "extendable": True},
                ],
            }})
        ])
        client = _client(session)
        res = client.proxies.list()

        method, url, _ = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example.test/api/account/proxies")
        self.assertIsNotNone(res.residential)
        self.assertEqual(res.residential.ports["http"], 12321)
        self.assertEqual(res.residential.traffic_gb_available, 4.5)
        self.assertEqual(res.subscription.status, "active")
        self.assertEqual(res.subscription.discount_pct, 10)
        self.assertEqual(len(res.orders), 1)
        self.assertEqual(res.orders[0].uuid, "o1")
        self.assertTrue(res.orders[0].auto_extend)


class ProxyPackagesTests(unittest.TestCase):
    def test_packages(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "packages": [{"gb": 5, "per_gb_cents": 200, "recommended": True}],
                "currency": "USD",
            }})
        ])
        client = _client(session)
        res = client.proxies.packages()
        self.assertEqual(session.calls[0][1], "https://api.example.test/api/account/proxies/packages")
        self.assertEqual(res.packages[0].gb, 5)
        self.assertEqual(res.packages[0].per_gb_cents, 200)
        self.assertTrue(res.packages[0].recommended)
        self.assertEqual(res.currency, "USD")


class ProxyEndpointsTests(unittest.TestCase):
    def test_endpoints_decodes_regions_ports_protocols(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "regions": [
                    {"code": "auto", "host": "proxy.eveses.com", "label": "Automatic (nearest)"},
                    {"code": "us", "host": "us.proxy.eveses.com", "label": "United States"},
                ],
                "ports": {"http": [12321, 11200], "socks5": [32325, 51200]},
                "protocols": ["http", "socks5"],
            }})
        ])
        client = _client(session)
        res = client.proxies.endpoints()

        method, url, _ = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example.test/api/account/proxies/endpoints")
        self.assertEqual(len(res.regions), 2)
        self.assertEqual(res.regions[0]["code"], "auto")
        self.assertEqual(res.ports["http"], [12321, 11200])
        self.assertEqual(res.ports["socks5"], [32325, 51200])
        self.assertEqual(res.protocols, ["http", "socks5"])
        self.assertEqual(res.raw["protocols"], ["http", "socks5"])


class ProxyQuoteTests(unittest.TestCase):
    def test_quote_residential_sends_params_and_decodes(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {
                "type": "residential", "gb": 5, "price_cents": 900,
                "currency": "USD", "per_gb_cents": 180, "discount_pct": 10,
            }})
        ])
        client = _client(session)
        q = client.proxies.quote(type="residential", gb=5, subscription=True)

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example.test/api/account/proxies/quote")
        self.assertEqual(kwargs["params"]["type"], "residential")
        self.assertEqual(kwargs["params"]["gb"], 5)
        self.assertEqual(kwargs["params"]["subscription"], "1")
        self.assertEqual(q.price_cents, 900)
        self.assertEqual(q.per_gb_cents, 180)
        self.assertEqual(q.raw["gb"], 5)


class ProxyPurchaseTests(unittest.TestCase):
    def test_purchase_static_sends_idempotency_and_body(self) -> None:
        session = _FakeSession([
            _FakeResponse(201, {"data": {
                "uuid": "o9", "type": "isp", "kind": "static", "quantity": 3,
                "status": "provisioning", "price_cents": 1500, "currency": "USD",
                "auto_extend": False, "extendable": True,
            }})
        ])
        client = _client(session)
        order = client.proxies.purchase(
            type="isp", product_id=1, plan_id=2, location_id=3, quantity=3,
            idempotency_key="idem-p1",
        )

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example.test/api/account/proxies/purchase")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "idem-p1")
        sent = json.loads(kwargs["data"])
        self.assertEqual(sent, {
            "type": "isp", "product_id": 1, "plan_id": 2,
            "location_id": 3, "quantity": 3,
        })
        self.assertEqual(order.uuid, "o9")
        self.assertEqual(order.price_cents, 1500)


class ProxyManagementTests(unittest.TestCase):
    def test_set_auto_renew_posts_enabled(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"uuid": "o1", "auto_extend": True, "type": "isp"}})
        ])
        client = _client(session)
        order = client.proxies.set_auto_renew("o1", True)

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example.test/api/account/proxies/o1/auto-renew")
        self.assertEqual(json.loads(kwargs["data"]), {"enabled": True})
        self.assertTrue(order.auto_extend)

    def test_extend_posts_days(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"uuid": "o1", "type": "isp", "status": "active"}})
        ])
        client = _client(session)
        order = client.proxies.extend("o1", days=60)
        method, url, kwargs = session.calls[0]
        self.assertEqual(url, "https://api.example.test/api/account/proxies/o1/extend")
        self.assertEqual(json.loads(kwargs["data"]), {"days": 60})
        self.assertEqual(order.uuid, "o1")

    def test_reset_sessions_posts_to_sessions_reset(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"reset": True})
        ])
        client = _client(session)
        client.proxies.reset_sessions()
        method, url, _ = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example.test/api/account/proxies/sessions/reset")

    def test_subscription_cancel(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"status": "cancelled", "gb": 5.0, "discount_pct": 0}})
        ])
        client = _client(session)
        sub = client.proxies.subscription_cancel()
        self.assertEqual(session.calls[0][1],
                         "https://api.example.test/api/account/proxies/subscription/cancel")
        self.assertEqual(sub.status, "cancelled")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
