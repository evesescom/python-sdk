"""
eveses — Official Python SDK.

Quickstart:

    from eveses import Eveses
    client = Eveses(api_key="sk_…")
    order = client.activations.create(country="ua", service="telegram")
    wallet = client.wallet.balance()
    services = client.catalog.services(mode="activation", country="ua")

Webhook verification:

    from eveses import Webhooks
    ok = Webhooks.verify(raw_body, signature_header, secret, timestamp=ts_header)
"""

from .activations import Activations, Order, OrderSms, OrderSmsBundle
from .captcha import Captcha, CaptchaSolution
from .catalog import (
    Catalog,
    CatalogCountriesResponse,
    CatalogPricingDuration,
    CatalogPricingResponse,
    CatalogServiceWithDurations,
    CatalogServicesResponse,
)
from .client import Eveses
from .emails import Emails
from .fingerprints import Fingerprint, Fingerprints
from .proxy import Proxy, ProxyList, ProxyOrder, ProxySubscription
from .trial import Trial
from .web_unblocker import WebUnblocker
from .exceptions import (
    EvesesAuthError,
    EvesesError,
    EvesesForbiddenError,
    EvesesNotFoundError,
    EvesesRateLimitError,
    EvesesServerError,
    EvesesValidationError,
)
from .wallet import Wallet, WalletBalance
from .webhooks import Webhooks, verify_webhook

__version__ = "0.3.0"

__all__ = [
    "Eveses",
    "Activations",
    "Captcha",
    "CaptchaSolution",
    "Catalog",
    "Emails",
    "Fingerprint",
    "Fingerprints",
    "Proxy",
    "ProxyList",
    "ProxyOrder",
    "ProxySubscription",
    "Trial",
    "Wallet",
    "WebUnblocker",
    "Webhooks",
    "verify_webhook",
    "Order",
    "OrderSms",
    "OrderSmsBundle",
    "WalletBalance",
    "CatalogCountriesResponse",
    "CatalogServicesResponse",
    "CatalogPricingResponse",
    "CatalogServiceWithDurations",
    "CatalogPricingDuration",
    "EvesesError",
    "EvesesAuthError",
    "EvesesForbiddenError",
    "EvesesNotFoundError",
    "EvesesValidationError",
    "EvesesRateLimitError",
    "EvesesServerError",
    "__version__",
]
