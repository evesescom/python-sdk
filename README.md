# eveses (Python SDK)

Official Python SDK for the [Eveses](https://eveses.com) developer API.
Activations, wallet, catalog (countries / services / pricing), and webhook signature verification.

## Install

```bash
pip install eveses
```

Requires Python 3.9+ and `requests`.

## Quickstart

```python
import os
from eveses import Eveses

client = Eveses(api_key=os.environ["EVESES_API_KEY"])

order = client.activations.create(
    country="ua",
    service="telegram",
    idempotency_key="my-uuid",
)
print(order.order_id, order.phone)

wallet = client.wallet.balance()
print(f"{wallet.available_balance / 100} {wallet.currency}")
```

## Authentication

Every request sends `Authorization: Bearer <api_key>`. Generate an API key from
your dashboard (`Settings → API keys`). The token is a Sanctum personal-access
token with `kind=api_key`.

## Activations

```python
order = client.activations.create(
    country="ua",
    service="telegram",
    mode="activation",            # or "rent"
    duration_minutes=60,          # rent only
    max_price_cents=100,          # optional ceiling
    idempotency_key="my-uuid",    # also sent as Idempotency-Key header
)

fresh = client.activations.get(order.order_id)
sms   = client.activations.sms(order.order_id)
#   sms.stored — delivered to us via upstream webhook
#   sms.fresh  — pulled from upstream provider on demand

client.activations.cancel(order.order_id)   # refund-where-supported
client.activations.finish(order.order_id)   # mark consumed
```

## Catalog (countries / services / pricing)

Read-only metadata for driving order-creation UX. All three calls hit the
API-key-authenticated `/api/v1/numbers/*` routes, so the same Bearer token
that creates orders can populate selectors and price tables.

```python
countries = client.catalog.countries(mode="activation").countries
services  = client.catalog.services(mode="activation", country="ua").services
pricing   = client.catalog.pricing(mode="activation", country="ua", service="telegram")
#   pricing.services[0].durations[0].price_cents → 50
```

`mode` accepts ``"activation"`` or ``"rent"``. For rentals, pass
``duration_minutes=...`` to ``pricing(...)`` to filter to a single duration.

## Webhook verification

Eveses signs every outbound webhook delivery with HMAC-SHA256 over
`f"{timestamp}.{raw_body}"`. Two headers carry the proof:

- `X-Eveses-Signature` — e.g. `sha256=abc123…`
- `X-Eveses-Timestamp` — unix seconds

Pass the **raw** request body (bytes or str) — not the parsed JSON. Re-serialising
through `json.loads` / `json.dumps` reorders keys and breaks the signature.

```python
# Flask example
from flask import Flask, request
from eveses import Webhooks

app = Flask(__name__)
SECRET = os.environ["EVESES_WEBHOOK_SECRET"]

@app.post("/eveses-webhook")
def eveses_webhook():
    raw = request.get_data()  # bytes
    if not Webhooks.verify(
        raw,
        request.headers.get("X-Eveses-Signature"),
        SECRET,
        timestamp=request.headers.get("X-Eveses-Timestamp"),
    ):
        return "bad signature", 401

    payload = request.get_json()
    # handle payload["event"] / payload["data"] …
    return "", 204
```

A functional alias is also exported:

```python
from eveses import verify_webhook
ok = verify_webhook(raw, sig_header, SECRET, timestamp=ts_header)
```

## Errors

All non-2xx responses raise a typed subclass of `EvesesError`:

| Status | Class |
| --- | --- |
| 400 / 422 | `EvesesValidationError` (with `.errors`) |
| 401 | `EvesesAuthError` |
| 403 | `EvesesForbiddenError` |
| 404 | `EvesesNotFoundError` |
| 429 | `EvesesRateLimitError` (only after the 1 auto-retry is exhausted) |
| 5xx | `EvesesServerError` |
| other | `EvesesError` |

```python
from eveses import EvesesValidationError

try:
    client.activations.create(country="", service="")
except EvesesValidationError as e:
    print(e.errors)
```

## API surface vs OpenAPI

The Eveses public OpenAPI spec exposes the customer-facing endpoints under
`/api/account/*` (legacy account scope) and `/api/v1/numbers/*` (new versioned
public API). For API-key consumers (`kind=api_key` Sanctum tokens), the v1
surface is currently a **thin wrapper** around the same controllers — orders
and wallet are still served from `/api/account/*`. This SDK targets the
account-scoped routes, which is where v1 reads & writes terminate today. When
v1 ships its own activations / wallet routes, you can override the base URL
without changing call sites; the response shapes are identical.

## Configuration

```python
client = Eveses(
    api_key="…",
    base_url="https://api.eveses.com",  # override per environment
    timeout=30.0,
    session=requests.Session(),         # inject for tests / connection pooling
    default_headers={"X-Trace-Id": "t1"},
    user_agent="my-app/1.2.3",
)
```

## Development

```bash
pip install -e '.[dev]'
python -m unittest discover -s tests
```

## License

MIT
