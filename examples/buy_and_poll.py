"""
buy_and_poll.py — Full activation lifecycle.

Run me
------
    pip install -e .
    export EVESES_API_KEY=sk_live_xxx
    python examples/buy_and_poll.py
    # Ctrl-C at any point to cancel the active order cleanly.

What it does
------------
1. Creates an activation order for COUNTRY/SERVICE.
2. Polls `sms()` every 5s for up to 5 minutes, looking for any incoming SMS.
3. When an SMS arrives, prints its text and calls `finish()` to release the
   number on the upstream provider and commit the spend.
4. On Ctrl-C OR poll timeout, calls `cancel()` to release the number and
   refund the held balance back to `available_balance`.

Gotchas
-------
- `sms()` returns BOTH `stored` (delivered to us via the provider's webhook)
  and `fresh` (pulled on demand). Use either; we union them here.
- Don't poll faster than the documented 5s minimum — the API will 429.
  The SDK auto-retries once on 429 using Retry-After but heavy polling
  burns through that allowance fast.
- Always `finish()` or `cancel()`. Leaving the order dangling ties up the
  held balance until expiry.
"""

from __future__ import annotations

import os
import time
import uuid

from eveses import (
    Eveses,
    EvesesError,
    EvesesNotFoundError,
    Order,
    OrderSms,
)

API_KEY = os.environ.get("EVESES_API_KEY", "sk_test_placeholder")
COUNTRY = os.environ.get("EVESES_COUNTRY", "ua")
SERVICE = os.environ.get("EVESES_SERVICE", "telegram")

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 5 * 60  # five minutes is plenty for most services


def collect_all_sms(stored: list[OrderSms], fresh: list[OrderSms]) -> list[OrderSms]:
    """De-duplicate the two SMS lists by id."""
    seen: set[int] = set()
    out: list[OrderSms] = []
    for sms in (*stored, *fresh):
        if sms.id in seen:
            continue
        seen.add(sms.id)
        out.append(sms)
    return out


def poll_for_sms(client: Eveses, order: Order) -> OrderSms | None:
    """
    Poll until we get an SMS, the timeout fires, or the user hits Ctrl-C.

    Returns the first SMS we see, or None if we timed out.
    """
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        bundle = client.activations.sms(order.order_id)
        messages = collect_all_sms(bundle.stored, bundle.fresh)
        if messages:
            return messages[0]
        print(
            f"  ...no SMS yet, sleeping {POLL_INTERVAL_S}s "
            f"(deadline in {int(deadline - time.monotonic())}s)"
        )
        time.sleep(POLL_INTERVAL_S)
    return None


def main() -> None:
    client = Eveses(api_key=API_KEY)
    order: Order | None = None

    try:
        order = client.activations.create(
            country=COUNTRY,
            service=SERVICE,
            idempotency_key=str(uuid.uuid4()),
        )
        print(f"Created order {order.order_id} → phone {order.phone}")
        print("Polling for SMS (Ctrl-C to cancel the order)…")

        sms = poll_for_sms(client, order)
        if sms is None:
            print("Timed out waiting for SMS — cancelling and refunding held balance.")
            client.activations.cancel(order.order_id)
            return

        print(f"Got SMS from {sms.sender or 'unknown'}: {sms.text!r}")
        finished = client.activations.finish(order.order_id)
        print(f"Order {finished.order_id} finished (status={finished.status}).")

    except KeyboardInterrupt:
        # Mid-poll cancellation. We MUST tell the server, otherwise the
        # held balance stays locked until the order expires server-side.
        print("\nCancellation requested — releasing the number…")
        if order is not None:
            try:
                client.activations.cancel(order.order_id)
                print("Cancelled cleanly.")
            except EvesesNotFoundError:
                # The order may already have moved to a terminal state
                # before our cancel landed.
                print("Order already in a terminal state; nothing to cancel.")
    except EvesesError as exc:
        print(f"SDK error ({exc.status}): {exc.message}")


if __name__ == "__main__":
    main()
