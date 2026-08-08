# eveses (Python SDK)

Official Python SDK for the [Eveses](https://eveses.com) developer API, built
for the versioned `/api/v1` surface. Numbers (SMS activations/rentals + catalog),
wallet, proxies, web-unblocker, temporary emails, free trials, captcha-solving,
a provider-agnostic marketplace, a unified orders feed, aggregate pricing /
quotas, the `me` principal, and webhook signature verification.

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

order = client.numbers.create(
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

## Numbers (SMS activations / rentals + catalog)

The former `activations` and `catalog` namespaces are merged into one
`numbers` module under `/api/v1/numbers/*`.

```python
order = client.numbers.create(
    country="ua",
    service="telegram",
    mode="activation",            # or "rent"
    duration_minutes=60,          # rent only
    max_price_cents=100,          # optional ceiling
    idempotency_key="my-uuid",    # also sent as Idempotency-Key header
)

fresh = client.numbers.get(order.order_id)
sms   = client.numbers.sms(order.order_id)
#   sms.stored — delivered to us via upstream webhook
#   sms.fresh  — pulled from upstream provider on demand

client.numbers.cancel(order.order_id)   # refund-where-supported
client.numbers.finish(order.order_id)   # mark consumed
client.numbers.retry(order.order_id)    # ask for another SMS
client.numbers.repeat(order.order_id)   # re-order the same country/service
client.numbers.auto_renew(order.order_id, True)   # rentals

client.numbers.list(status="active")    # native per-service history
client.numbers.summary()                # aggregate counts / totals
client.numbers.batch([{"country": "ua", "service": "telegram"}])
```

### Catalog (countries / services / pricing)

Read-only metadata for driving order-creation UX, on the same module:

```python
countries = client.numbers.countries(mode="activation").countries
services  = client.numbers.services(mode="activation", country="ua").services
pricing   = client.numbers.pricing(mode="activation", country="ua", service="telegram")
#   pricing.services[0].durations[0].price_cents → 50

client.numbers.carriers(country="us")   # operators for a country
client.numbers.states(country="us")     # states/regions where supported
```

`mode` accepts ``"activation"`` or ``"rent"``. For rentals, pass
``duration_minutes=...`` to ``pricing(...)`` to filter to a single duration.
(`services` is an alias of `products`.)

## Proxies

Buy and manage residential (metered, per-GB) and static (per-IP: ISP /
datacenter / IPv6 / sneaker / mobile) proxies. The upstream provider stays
invisible — connection details come back on the white-label host. Hits
`/api/v1/proxy/*`.

```python
# Browse
client.proxy.pricing()                         # residential GB ladder + static catalogue
client.proxy.endpoints()                       # white-label subdomains + ports
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
one     = client.proxy.get(order.uuid)          # a single order by UUID
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
`/api/v1/webunblocker/*`.

```python
client.web_unblocker.pricing()
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
`/api/v1/emails/*`.

```python
client.emails.pricing(site="example.com")        # domains under the `domains` key
client.emails.quote("mail.example", provider="…")

box = client.emails.purchase("mail.example", idempotency_key="my-uuid")
address = box["email"]

client.emails.list(include_released=False)
client.emails.get(address)
client.emails.messages(address, page=1, per_page=20)
client.emails.mark_read(address, message_id=123)
client.emails.release(address)                   # delete the address
```

## Trial

Query and activate free-trial access for individual services. Hits
`/api/v1/trial/*`.

```python
client.trial.status()                            # eligibility / used / expires_at
client.trial.subscribe(["telegram", "whatsapp"])
```

## Captcha

Resells 2captcha, billed pay-per-use from the wallet (count-on-success). The
`solve` call is blocking: it submits the task then polls the result endpoint —
honouring the API's `retry_after` — until the task is ready. Hits
`/api/v1/captcha/*`.

```python
solution = client.captcha.solve(
    "recaptcha_v2",
    {"sitekey": "…", "pageurl": "https://example.com"},
    idempotency_key="my-uuid",
    timeout_sec=180,
)
print(solution.solution, solution.price_micro_usd)
# raises EvesesError on failure or timeout

client.captcha.result(task_id)   # single, non-blocking poll
client.captcha.rates()           # per-solve retail rates by type
client.captcha.usage(status="ready")   # cursor-paginated task history
```

## Orders, pricing, quotas

Cross-product read surfaces for dashboards.

```python
# Unified order history (numbers | proxy | webunblocker | emails; NOT captcha)
feed = client.orders.list(service="proxy,emails", status="active", limit=50)
one  = client.orders.get("b1f2…-uuid")     # normalized OrderView for any product

prices = client.pricing.all()               # every product's prices in one call
quotas = client.quotas.all()                # remaining prepaid balances
```

## Me

```python
me = client.me.get()
print(me.abilities)          # e.g. ["*"]
print(me.features)           # {"trial": True, "proxy": True, "captcha": False, …}
# Use me.features to gate product entry points instead of build-time flags.

client.me.loyalty()          # loyalty tier / weekly-spend status
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
    client.numbers.create(country="", service="")
except EvesesValidationError as e:
    print(e.errors)
```

## API surface

Every authenticated call targets the versioned `/api/v1/*` surface. The base
URL is unchanged (`…/api`); only the per-call path string changed from the old
`/api/account/*` scope. Auth is unchanged — keep sending the Sanctum bearer
token. Every `/v1` response also carries `RateLimit-Limit` / `RateLimit-Remaining`
/ `RateLimit-Reset` headers (plus `Retry-After` on a 429) for backoff.

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
python -m pytest
```

## Changelog

### 0.5.0

- **New `marketplace` namespace** — browse a normalized, provider-agnostic
  catalog (`catalog`, `categories`, `filters`) and purchase (`quote`, `buy`,
  `orders`, `order`, `reveal`). The public `catalog` supports attribute filters
  (`country`/`origin`/`format`/`twofa`) and `group_by` = `country` |
  `attributes` (same-type products collapse into groups carrying
  `prices_cents` variants).
- **New `proxy.locations_detail(country, type)`** — per-country residential
  state/city/ISP geo drill-down.
- Default user-agent bumped to `eveses-python/0.5.0`.

### 0.4.0

- **Repointed the whole SDK to the versioned `/api/v1/*` surface** (from the
  legacy `/api/account/*` scope).
- **Merged `activations` + `catalog` → one `numbers` namespace** under
  `/api/v1/numbers/*`: `create`, `get`, `sms`, `cancel`, `finish`, `retry`,
  `repeat`, `auto_renew`, `list`, `summary`, `batch`, plus catalog `pricing`,
  `countries`, `products`/`services`, `carriers`, `states`.
- `proxy` → `/api/v1/proxy/*`: buy/list on `/orders`, `get(uuid)`,
  extend/auto_renew under `/orders/{uuid}`, and `pricing` (replaces the old
  `packages`/`catalog`).
- `web_unblocker` → `/api/v1/webunblocker/*`: buy/list on `/orders`, `pricing`.
- `emails` → `/api/v1/emails/*`: buy/list on `/orders`, `pricing`; inbox keyed
  by email address.
- `captcha` → `/api/v1/captcha/*`; added `result`, `rates`, and `usage`.
- **New `orders` namespace** — unified cross-product order history
  (`GET /api/v1/orders`, `…/{uuid}`).
- **New `pricing` namespace** — aggregate price sheet (`GET /api/v1/pricing`).
- **New `quotas` namespace** — remaining prepaid balances (`GET /api/v1/quotas`).
- **New `me` namespace** — the principal, now carrying `abilities` + `features`.
- **Removed the `fingerprints` product** entirely.

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
