"""
Tests for the Eveses Python SDK.

Uses the stdlib `unittest` runner so the test suite has zero external deps
beyond what the SDK already imports (`requests`).

Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

from eveses import (
    Eveses,
    EvesesAuthError,
    EvesesValidationError,
    Webhooks,
    verify_webhook,
)


class _FakeResponse:
    """Mimics enough of `requests.Response` for the SDK's parser."""

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
    """A drop-in for `requests.Session` that records calls and returns canned responses."""

    def __init__(self, responses: List[_FakeResponse]) -> None:
        self._queue = list(responses)
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append((method, url, kwargs))
        if not self._queue:
            raise AssertionError("FakeSession: no more responses queued")
        return self._queue.pop(0)


class ActivationsTests(unittest.TestCase):
    def test_create_sends_bearer_idempotency_and_maps_response(self) -> None:
        session = _FakeSession([
            _FakeResponse(
                200,
                {
                    "data": {
                        "order_id": "01HABC",
                        "status": "waiting_sms",
                        "phone": "+380635551822",
                        "price_cents": 50,
                        "expires_at": "2026-05-05T12:00:00Z",
                    }
                },
            )
        ])
        client = Eveses(api_key="sk_test", base_url="https://api.example.test", session=session)

        order = client.activations.create(
            country="ua",
            service="telegram",
            idempotency_key="idem-1",
            max_price_cents=100,
        )

        self.assertEqual(len(session.calls), 1)
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example.test/api/account/orders")
        headers = kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer sk_test")
        self.assertEqual(headers["Idempotency-Key"], "idem-1")
        self.assertEqual(headers["Content-Type"], "application/json")
        sent = json.loads(kwargs["data"])
        self.assertEqual(
            sent,
            {
                "mode": "activation",
                "country": "ua",
                "service": "telegram",
                "idempotency_key": "idem-1",
                "max_price_cents": 100,
            },
        )

        self.assertEqual(order.order_id, "01HABC")
        self.assertEqual(order.status, "waiting_sms")
        self.assertEqual(order.price_cents, 50)

    def test_429_triggers_one_retry(self) -> None:
        session = _FakeSession([
            _FakeResponse(429, {"message": "slow down"}, headers={"Retry-After": "0"}),
            _FakeResponse(200, {"data": {"order_id": "X", "status": "waiting_sms"}}),
        ])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        with patch("eveses.client.time.sleep"):  # don't actually sleep in tests
            order = client.activations.get("X")
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(order.order_id, "X")

    def test_401_raises_auth_error(self) -> None:
        session = _FakeSession([_FakeResponse(401, {"message": "Unauthenticated."})])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        with self.assertRaises(EvesesAuthError) as ctx:
            client.wallet.balance()
        self.assertEqual(ctx.exception.status, 401)

    def test_422_raises_validation_error_with_field_map(self) -> None:
        session = _FakeSession([
            _FakeResponse(
                422,
                {
                    "message": "The country field is required.",
                    "errors": {"country": ["required"]},
                },
            )
        ])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        with self.assertRaises(EvesesValidationError) as ctx:
            client.activations.create(country="", service="telegram")
        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.errors, {"country": ["required"]})


class WalletTests(unittest.TestCase):
    def test_balance_maps_snake_case_fields(self) -> None:
        session = _FakeSession([
            _FakeResponse(
                200,
                {
                    "data": {
                        "balance": 12500,
                        "held_balance": 250,
                        "available_balance": 12250,
                        "currency": "USD",
                    }
                },
            )
        ])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        w = client.wallet.balance()
        self.assertEqual(w.balance, 12500)
        self.assertEqual(w.held_balance, 250)
        self.assertEqual(w.available_balance, 12250)
        self.assertEqual(w.currency, "USD")


class WebhookTests(unittest.TestCase):
    def test_verify_accepts_valid_signature_within_tolerance(self) -> None:
        secret = "whsec_test"
        body = json.dumps({"event": "order.sms_received", "data": {"order_id": "X"}})
        ts = int(time.time())
        sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()

        self.assertTrue(Webhooks.verify(body, sig, secret, timestamp=ts))
        self.assertFalse(Webhooks.verify(body, sig, "wrong-secret", timestamp=ts))
        self.assertFalse(Webhooks.verify(body + "tamper", sig, secret, timestamp=ts))

    def test_verify_rejects_stale_timestamp(self) -> None:
        secret = "whsec_test"
        body = "{}"
        ts = int(time.time()) - 10_000
        sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
        self.assertFalse(Webhooks.verify(body, sig, secret, timestamp=ts))
        # Tolerance disabled -> passes.
        self.assertTrue(Webhooks.verify(body, sig, secret, timestamp=ts, tolerance_seconds=0))

    def test_module_level_alias_matches(self) -> None:
        secret = "whsec"
        body = "{}"
        ts = int(time.time())
        sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook(body, sig, secret, timestamp=ts))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
