"""
eveses — Official Python SDK.

Quickstart:

    from eveses import Eveses
    client = Eveses(api_key="sk_…")
    order = client.numbers.create(country="ua", service="telegram")
    wallet = client.wallet.balance()
    services = client.numbers.services(mode="activation", country="ua")

Webhook verification:

    from eveses import Webhooks
    ok = Webhooks.verify(raw_body, signature_header, secret, timestamp=ts_header)
"""

from .captcha import Captcha, CaptchaSolution
from .client import Eveses
from .emails import Emails
from .marketplace import Marketplace
from .me import Me, MeProfile
from .numbers import (
    CatalogCountriesResponse,
    CatalogPricingDuration,
    CatalogPricingResponse,
    CatalogServiceWithDurations,
    CatalogServicesResponse,
    Numbers,
    Order,
    OrderSms,
    OrderSmsBundle,
)
from .orders import Orders
from .pricing import Pricing
from .proxy import Proxy, ProxyList, ProxyOrder, ProxySubscription
from .quotas import Quotas
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

__version__ = "0.5.0"

__all__ = [
    "Eveses",
    "Numbers",
    "Captcha",
    "CaptchaSolution",
    "Emails",
    "Marketplace",
    "Me",
    "MeProfile",
    "Orders",
    "Pricing",
    "Proxy",
    "ProxyList",
    "ProxyOrder",
    "ProxySubscription",
    "Quotas",
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
