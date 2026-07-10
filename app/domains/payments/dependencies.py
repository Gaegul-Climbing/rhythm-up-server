from typing import Annotated

from fastapi import Depends

from app.cache.redis import redis_client
from app.core.config import get_settings
from app.domains.payments.providers.base import (
    ControllablePaymentProvider,
    PaymentProvider,
)
from app.domains.payments.providers.local import LocalPaymentProvider
from app.domains.payments.providers.toss import TossPaymentProvider

settings = get_settings()
local_payment_provider = LocalPaymentProvider(
    redis_client,
    prefix=settings.redis_key_prefix,
    ttl_seconds=settings.local_payment_state_ttl_seconds,
)
toss_payment_provider = TossPaymentProvider(
    secret_key=settings.toss_payments_secret_key,
    base_url=settings.toss_payments_base_url,
    api_version=settings.toss_payments_api_version,
)


def get_payment_provider() -> PaymentProvider:
    if settings.payment_provider == "toss":
        return toss_payment_provider
    return local_payment_provider


def get_controllable_payment_provider() -> ControllablePaymentProvider:
    return local_payment_provider


PaymentProviderDependency = Annotated[PaymentProvider, Depends(get_payment_provider)]
ControllablePaymentProviderDependency = Annotated[
    ControllablePaymentProvider,
    Depends(get_controllable_payment_provider),
]
