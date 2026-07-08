"""
proxies_unblocker_emails.py — tour of the three product modules added to the
Eveses Python SDK: proxies, web_unblocker, emails.

Run me
------
    pip install -e .                  # from sdk/python/
    export EVESES_API_KEY=sk_live_xxx # your sk_ token from the dashboard
    python examples/proxies_unblocker_emails.py

What it does
------------
Each block is defensive: it quotes first (a cheap read), then only *buys* when
EVESES_BUY=1 is set, so running the script by accident never spends money. All
prices are integer cents; currency is always "USD".

Idempotency note
----------------
Every purchase takes an `idempotency_key`. Generate it once per *user intent*
(e.g. when the user clicks "Buy"), not per HTTP attempt, so a retried request
returns the SAME order instead of charging twice.
"""

from __future__ import annotations

import os
import uuid

from eveses import Eveses, EvesesError

API_KEY = os.environ.get("EVESES_API_KEY", "sk_test_placeholder")
BUY = os.environ.get("EVESES_BUY") == "1"


def proxies(client: Eveses) -> None:
    print("== Proxies ==")
    overview = client.proxies.list()
    if overview.residential:
        r = overview.residential
        print(f"  residential: {r.traffic_gb_available:.2f} GB available")
    print(f"  {len(overview.orders)} recent order(s)")

    # Residential (metered / GB) quote.
    q = client.proxies.quote(type="residential", gb=5)
    print(f"  5 GB residential ≈ {q.price_cents} cents {q.currency}")

    if BUY:
        order = client.proxies.purchase(
            type="residential", gb=5, idempotency_key=str(uuid.uuid4()),
        )
        print(f"  bought {order.uuid} ({order.status})")
        # Static per-IP orders can auto-renew; residential uses the subscription.
        # client.proxies.set_auto_renew(order.uuid, True)


def web_unblocker(client: Eveses) -> None:
    print("== Web Unblocker ==")
    overview = client.web_unblocker.list()
    if overview.access:
        print(f"  {overview.access.requests_remaining} requests remaining")

    q = client.web_unblocker.quote(requests=10_000)
    print(f"  10k requests ≈ {q.price_cents} cents ({q.per_1k_cents}/1k)")

    if BUY:
        order = client.web_unblocker.purchase(
            requests=10_000, idempotency_key=str(uuid.uuid4()),
        )
        print(f"  bought {order.uuid} ({order.requests} requests)")


def emails(client: Eveses) -> None:
    print("== Emails ==")
    domains = client.emails.domains().domains
    print(f"  {len(domains)} rentable domain(s)")
    if not domains:
        return

    pick = domains[0]
    q = client.emails.quote(domain=str(pick.domain), provider=pick.provider)
    print(f"  {pick.domain} ≈ {q.price_cents} cents {q.currency}")

    if BUY:
        addr = client.emails.purchase(
            domain=str(pick.domain), provider=pick.provider,
            idempotency_key=str(uuid.uuid4()),
        )
        print(f"  rented {addr.address} ({addr.uuid})")
        # get() also live-syncs reseller inboxes — poll it for new mail.
        inbox = client.emails.get(addr.uuid)
        print(f"  {len(inbox.messages)} message(s) so far")


def main() -> None:
    client = Eveses(api_key=API_KEY)
    if not BUY:
        print("(read-only — set EVESES_BUY=1 to actually purchase)\n")
    try:
        proxies(client)
        web_unblocker(client)
        emails(client)
    except EvesesError as exc:
        print(f"SDK error ({exc.status}): {exc.message}")


if __name__ == "__main__":
    main()
