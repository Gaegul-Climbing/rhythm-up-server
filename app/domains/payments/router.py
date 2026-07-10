import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request, status

from app.core.config import get_settings
from app.database.dependencies import SessionDependency
from app.domains.accounts.dependencies import CurrentUserDependency
from app.domains.payments.dependencies import (
    ControllablePaymentProviderDependency,
    PaymentProviderDependency,
)
from app.domains.payments.models import PaymentStatus
from app.domains.payments.providers.base import ProviderPaymentStatus
from app.domains.payments.schemas import (
    MockPaymentCompleteRequest,
    MockPaymentCompleteResponse,
    PaymentCheckoutResponse,
    PaymentCreateRequest,
    PaymentOrderCreateRequest,
    PaymentOrderResponse,
    PaymentResponse,
    TossPaymentConfirmRequest,
)
from app.domains.payments.service import (
    cancel_payment,
    confirm_toss_payment,
    create_order,
    find_order,
    find_payment,
    process_provider_event,
    reconcile_payment,
    request_payment,
)
from app.domains.reservations.dependencies import HoldStoreDependency

logger = logging.getLogger(__name__)

router = APIRouter()
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)]


def build_payment_response(payment, *, checkout: PaymentCheckoutResponse | None = None):
    response = PaymentResponse.model_validate(payment)
    response.checkout = checkout
    return response


def build_toss_checkout(payment, request: Request | None = None) -> PaymentCheckoutResponse | None:
    if payment.provider != "toss" or payment.status != PaymentStatus.PENDING:
        return None
    settings = get_settings()
    success_url = settings.toss_payments_success_url
    fail_url = settings.toss_payments_fail_url
    if request is not None:
        origin = str(request.base_url).rstrip("/")
        success_url = f"{origin}/?paymentResult=success"
        fail_url = f"{origin}/?paymentResult=fail"
    return PaymentCheckoutResponse(
        provider="toss",
        client_key=settings.toss_payments_client_key,
        order_id=str(payment.order_id),
        order_name=f"RhythmUp practice room reservation {str(payment.order_id)[:8]}",
        amount=payment.amount,
        currency="KRW",
        success_url=success_url,
        fail_url=fail_url,
    )


@router.post(
    "/payment-orders", response_model=PaymentOrderResponse, status_code=status.HTTP_201_CREATED
)
async def create_payment_order(
    request: PaymentOrderCreateRequest,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
) -> PaymentOrderResponse:
    order = await create_order(
        session=session,
        store=store,
        user_id=current_user.id,
        hold_id=request.hold_id,
        idempotency_key=idempotency_key,
    )
    return PaymentOrderResponse.model_validate(order)


@router.get("/payment-orders/{order_id}", response_model=PaymentOrderResponse)
async def read_payment_order(
    order_id: UUID,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> PaymentOrderResponse:
    return PaymentOrderResponse.model_validate(await find_order(session, current_user.id, order_id))


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    request: PaymentCreateRequest,
    http_request: Request,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
    provider: PaymentProviderDependency,
) -> PaymentResponse:
    payment = await request_payment(
        session=session,
        store=store,
        provider=provider,
        user_id=current_user.id,
        order_id=request.order_id,
        idempotency_key=idempotency_key,
    )
    logger.info(
        "Payment API created payment: payment_id=%s order_id=%s provider=%s checkout_provider=%s",
        payment.id,
        payment.order_id,
        payment.provider,
        build_toss_checkout(payment, http_request).provider
        if build_toss_checkout(payment, http_request)
        else None,
    )
    return build_payment_response(payment, checkout=build_toss_checkout(payment, http_request))


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def read_payment(
    payment_id: UUID,
    http_request: Request,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> PaymentResponse:
    payment = await find_payment(session, current_user.id, payment_id)
    return build_payment_response(payment, checkout=build_toss_checkout(payment, http_request))


@router.post("/payments/toss/confirm", response_model=PaymentResponse)
async def confirm_toss(
    request: TossPaymentConfirmRequest,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
    provider: PaymentProviderDependency,
) -> PaymentResponse:
    logger.info(
        "Toss confirm API received: order_id=%s amount=%s has_payment_key=%s",
        request.order_id,
        request.amount,
        bool(request.payment_key),
    )
    payment = await confirm_toss_payment(
        session=session,
        store=store,
        provider=provider,
        user_id=current_user.id,
        order_id=request.order_id,
        payment_key=request.payment_key,
        amount=request.amount,
        idempotency_key=idempotency_key,
    )
    return build_payment_response(payment)


@router.post("/payments/{payment_id}/reconcile", response_model=PaymentResponse)
async def reconcile(
    payment_id: UUID,
    http_request: Request,
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
    provider: PaymentProviderDependency,
) -> PaymentResponse:
    payment = await reconcile_payment(
        session=session,
        store=store,
        provider=provider,
        user_id=current_user.id,
        payment_id=payment_id,
    )
    return build_payment_response(payment, checkout=build_toss_checkout(payment, http_request))


@router.delete("/payments/{payment_id}", response_model=PaymentResponse)
async def delete_payment(
    payment_id: UUID,
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
    provider: PaymentProviderDependency,
) -> PaymentResponse:
    payment = await cancel_payment(
        session=session,
        store=store,
        provider=provider,
        user_id=current_user.id,
        payment_id=payment_id,
    )
    return build_payment_response(payment)


@router.post(
    "/mock-payment-provider/payments/{payment_id}/complete",
    response_model=MockPaymentCompleteResponse,
)
async def complete_mock_payment(
    payment_id: UUID,
    request: MockPaymentCompleteRequest,
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
    provider: ControllablePaymentProviderDependency,
) -> MockPaymentCompleteResponse:
    payment = await find_payment(session, current_user.id, payment_id)
    outcome = ProviderPaymentStatus(request.outcome.value)
    event = await provider.complete_payment(payment.provider_payment_id, outcome)
    if request.deliver_event:
        payment = await process_provider_event(
            session=session,
            store=store,
            provider=provider,
            event=event,
        )
    return MockPaymentCompleteResponse(
        provider_payment_id=event.payment_id,
        provider_status=event.status.value,
        event_id=event.id,
        event_delivered=request.deliver_event,
        payment=PaymentResponse.model_validate(payment),
    )
