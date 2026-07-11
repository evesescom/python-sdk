# eveses (Python SDK)

Official Python SDK for the [Eveses](https://eveses.com) developer API.
Activations, wallet, catalog (countries / services / pricing), proxies,
web-unblocker, temporary emails, free trials, captcha-solving, browser
fingerprints, and webhook signature verification.

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

## Proxies

Buy and manage residential (metered, per-GB) and static (per-IP: ISP /
datacenter / IPv6 / sneaker / mobile) proxies. The upstream provider stays
invisible — connection details come back on the white-label host. Hits
`/api/account/proxies/*`.

```python
# Browse
client.proxy.packages()                       # residential GB ladder
client.proxy.endpoints()                       # white-label subdomains + ports
client.proxy.catalog()                         # static per-IP products/plans
client.proxy.locations(type="residential")     # available targeting
client.proxy.quote(type="residential", gb=5)   # estimate before buying

# Buy
order = client.proxy.purchase(
    type="residential",
    gb=5,
    subscription=False,          # start a monthly residential subscription
    idempotency_key="my-uuid",
)
# static per-IP:
# client.proxy.purchase(type="isp", product_id=1, plan_id=2, location_id=3, quantity=2)

# Manage
listing = client.proxy.list()                  # residential + subscription + orders
client.proxy.usage(from_="2026-06-01", to="2026-06-24")
client.proxy.extend(order.uuid, days=30)        # static per-IP order
client.proxy.auto_renew(order.uuid, enabled=True)
client.proxy.reset_sessions()                   # rotate residential sticky sessions
client.proxy.trial()                            # one-time proxy free trial

# Residential subscription
client.proxy.subscription_pause()
client.proxy.subscription_resume()
client.proxy.subscription_cancel()
```

## Web Unblocker

Buy and manage a web-unblocker subscription (metered by request count). Hits
`/api/account/web-unblocker/*`.

```python
client.web_unblocker.packages()
client.web_unblocker.quote(10_000, subscription=False)
client.web_unblocker.access()                   # credentials + endpoints

client.web_unblocker.purchase(10_000, subscription=False, idempotency_key="my-uuid")
client.web_unblocker.trial()                    # one-time free trial

client.web_unblocker.subscription_pause()
client.web_unblocker.subscription_resume()
client.web_unblocker.subscription_cancel()
```

## Emails

Buy and manage temporary email addresses and browse received messages. Hits
`/api/account/emails/*`.

```python
client.emails.domains(site="example.com")
client.emails.quote("mail.example", provider="…")

box = client.emails.purchase("mail.example", idempotency_key="my-uuid")
uuid = box["uuid"]

client.emails.list(include_released=False)
client.emails.get(uuid)
client.emails.messages(uuid, page=1, per_page=20)
client.emails.mark_read(uuid, message_id=123)
client.emails.release(uuid)                      # delete the address
```

## Trial

Query and activate free-trial access for individual services. Hits
`/api/account/trial/*`.

```python
client.trial.status()                            # eligibility / used / expires_at
client.trial.subscribe(["telegram", "whatsapp"])
```

## Captcha

Resells 2captcha, billed pay-per-use from the wallet (count-on-success). The
`solve` call is blocking: it submits the task then polls the result endpoint —
honouring the API's `retry_after` — until the task is ready. Hits
`/api/account/captcha/*`.

```python
solution = client.captcha.solve(
    "recaptcha_v2",
    {"sitekey": "…", "pageurl": "https://example.com"},
    idempotency_key="my-uuid",
    timeout_sec=180,
)
print(solution.solution, solution.price_micro_usd)
# raises EvesesError on failure or timeout
```

## Fingerprints

Resells 2captcha's Fingerprint API, billed pay-per-use (count-on-success).
Unlike captcha-solving this is synchronous — one request returns a complete
fingerprint. Hits `/api/account/fingerprints/*`.

```python
fp = client.fingerprints.generate({"os": "windows", "browser": "chrome"})
print(fp.fingerprint, fp.price_micro_usd)

rand = client.fingerprints.random()
```

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

## Changelog

### 0.3.0

- New `proxy` namespace: residential (per-GB) and static per-IP proxies —
  `packages`, `endpoints`, `catalog`, `locations`, `quote`, `usage`, `list`,
  `purchase`, `extend`, `auto_renew`, `reset_sessions`, `trial`, and residential
  subscription `pause`/`resume`/`cancel`. Exposes `Proxy`, `ProxyOrder`,
  `ProxySubscription`, `ProxyList`.
- New `web_unblocker` namespace: `packages`, `quote`, `access`, `purchase`,
  `trial`, and subscription `pause`/`resume`/`cancel`.
- New `emails` namespace: temporary email addresses — `domains`, `quote`,
  `list`, `get`, `messages`, `purchase`, `mark_read`, `release`.
- New `trial` namespace: `status` and `subscribe` for per-service free trials.
- New `captcha` namespace: blocking `solve` (submit + poll) reselling 2captcha,
  billed pay-per-use. Exposes `Captcha`, `CaptchaSolution`.
- New `fingerprints` namespace: synchronous `generate` / `random` browser
  fingerprints. Exposes `Fingerprints`, `Fingerprint`.
- Module reorg: the old `proxies` module was replaced by `proxy`.

### 0.2.0

- Activations, wallet, catalog (countries / services / pricing), and webhook
  signature verification.

## License

MIT
