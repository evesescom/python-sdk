# Eveses Python SDK — examples

Three runnable scripts that exercise the SDK end-to-end. They use only
stdlib + the SDK itself (which pulls in `requests`).

| File | What it shows |
| --- | --- |
| `quickstart.py` | Construct the client, check wallet balance, list services, buy ONE activation with an idempotency key. |
| `buy_and_poll.py` | Full activation lifecycle: create → poll SMS every 5s for 5 min → `finish()` (or `cancel()` on Ctrl-C / timeout). |
| `webhook_server.py` | Minimal `http.server` endpoint that verifies `X-Eveses-Signature` with `Webhooks.verify` and prints the parsed payload. |
| `proxies_unblocker_emails.py` | Tour of the proxies / web_unblocker / emails modules: quote everything, and buy only when `EVESES_BUY=1`. |

## Prerequisites

```bash
# Install the SDK in editable mode from sdk/python/
pip install -e .

# Get a Sanctum API-key token (kind=api_key) from the Eveses dashboard.
export EVESES_API_KEY=sk_live_xxx

# For the webhook server only:
export EVESES_WEBHOOK_SECRET=whsec_xxx
```

Run any example with `python examples/<name>.py`.
