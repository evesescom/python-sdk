"""
Webhook signature verification.

Eveses signs every webhook delivery with HMAC-SHA256 over `f"{timestamp}.{body}"`,
using the endpoint's signing secret. Two headers carry the proof:

    X-Eveses-Signature  -> "sha256=<hex>"
    X-Eveses-Timestamp  -> unix seconds

Use `Webhooks.verify(...)`. Always pass the **raw** request body (bytes or str),
not the parsed JSON — round-tripping through json.loads/json.dumps reorders
keys and breaks the signature.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional, Union


class Webhooks:
    """Static-like helpers for webhook verification."""

    @staticmethod
    def verify(
        raw_body: Union[str, bytes],
        signature_header: Optional[str],
        secret: str,
        *,
        timestamp: Optional[Union[str, int, float]] = None,
        tolerance_seconds: int = 300,
    ) -> bool:
        """
        Verify an Eveses webhook signature.

        :param raw_body:         The raw request body (str or bytes).
        :param signature_header: Value of `X-Eveses-Signature`, e.g. "sha256=abc123".
        :param secret:           The endpoint signing secret.
        :param timestamp:        Value of `X-Eveses-Timestamp` (unix seconds).
        :param tolerance_seconds: Reject timestamps drifting more than this from now.
                                  Pass 0 to disable the staleness check.
        :returns:                True iff the signature is valid and within tolerance.
        """
        if not signature_header or not secret:
            return False

        expected_hex = _strip_prefix(signature_header)
        if not expected_hex or not all(c in "0123456789abcdefABCDEF" for c in expected_hex):
            return False

        if timestamp is None or timestamp == "":
            return False
        try:
            ts = int(timestamp)
        except (TypeError, ValueError):
            try:
                ts = int(float(timestamp))
            except (TypeError, ValueError):
                return False
        if ts <= 0:
            return False

        if tolerance_seconds > 0:
            now = int(time.time())
            if abs(now - ts) > tolerance_seconds:
                return False

        body_bytes = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
        signing_input = f"{ts}.".encode("utf-8") + body_bytes
        computed = hmac.new(
            secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed, expected_hex.lower())


def _strip_prefix(value: str) -> str:
    trimmed = value.strip()
    return trimmed[len("sha256=") :] if trimmed.startswith("sha256=") else trimmed


# Module-level convenience alias matching the spec's `verify_webhook(...)`.
def verify_webhook(
    raw_body: Union[str, bytes],
    signature_header: Optional[str],
    secret: str,
    *,
    timestamp: Optional[Union[str, int, float]] = None,
    tolerance_seconds: int = 300,
) -> bool:
    """Functional alias for :py:meth:`Webhooks.verify`."""
    return Webhooks.verify(
        raw_body,
        signature_header,
        secret,
        timestamp=timestamp,
        tolerance_seconds=tolerance_seconds,
    )
