"""
webhook_server.py — Minimal stdlib HTTP server that verifies Eveses webhooks.

Run me
------
    export EVESES_WEBHOOK_SECRET=whsec_xxx   # from your endpoint settings
    export PORT=8787                          # optional, defaults to 8787
    python examples/webhook_server.py
    # Then point Eveses at  http://localhost:8787/eveses/webhook
    # (use ngrok / cloudflared in real life — Eveses needs a public URL).

What it does
------------
- Listens on POST /eveses/webhook
- Reads the raw body BEFORE any JSON parsing (signature is over raw bytes —
  json.loads + json.dumps would reorder keys and break the HMAC).
- Calls Webhooks.verify() with the X-Eveses-Signature + X-Eveses-Timestamp
  headers. Default tolerance is 300s — anything older is rejected (replay
  protection).
- Returns 200 on success, 401 on bad signature, 400 on malformed body.

Gotchas
-------
- `Webhooks.verify` is intentionally side-effect free: it returns False
  for ANY failure (missing header, bad hex, expired timestamp). Don't
  treat False as "an error" — it just means "not a valid Eveses delivery".
- Replay-protection window is 300s by default. Don't widen it unless you
  have idempotent handlers and a very good reason; widening lets attackers
  replay old captured deliveries.
- Respond to Eveses within ~10s. If your handler does heavy work, enqueue
  the parsed payload and return 200 immediately.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from eveses import Webhooks

WEBHOOK_SECRET = os.environ.get("EVESES_WEBHOOK_SECRET", "whsec_placeholder")
PORT = int(os.environ.get("PORT", "8787"))
PATH = "/eveses/webhook"


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 — stdlib name
        if self.path != PATH:
            self._respond(404, {"error": "not_found"})
            return

        # Read the raw body. The Content-Length header is mandatory in
        # HTTP/1.1 for bodies; we trust it because the signature is what
        # actually authenticates the payload.
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length) if length > 0 else b""

        # Header names are case-insensitive in HTTP; BaseHTTPRequestHandler
        # already lowercases lookups, but we use the canonical casing for
        # readability.
        signature = self.headers.get("X-Eveses-Signature")
        timestamp = self.headers.get("X-Eveses-Timestamp")

        ok = Webhooks.verify(
            raw_body,
            signature,
            WEBHOOK_SECRET,
            timestamp=timestamp,
            tolerance_seconds=300,
        )
        if not ok:
            # Don't leak details about which check failed — that's a
            # signature-forgery oracle.
            self._respond(401, {"error": "invalid_signature"})
            return

        try:
            payload = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid_json"})
            return

        event_type = payload.get("type", "?")
        print(f"Received verified webhook: type={event_type}")
        print(json.dumps(payload, indent=2, sort_keys=True))

        # ACK fast. Real handlers should enqueue the event and respond here.
        self._respond(200, {"received": True})

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: ANN401
        # Quiet the default per-request stderr noise.
        return

    def _respond(self, status: int, body: dict[str, object]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Listening on http://0.0.0.0:{PORT}{PATH}")
    print("Configure this URL on your Eveses webhook endpoint.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
