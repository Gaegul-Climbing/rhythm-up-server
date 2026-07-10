import base64
import logging
from typing import Any
from uuid import UUID

import httpx

from app.domains.payments.providers.base import (
    ProviderEvent,
    ProviderPayment,
    ProviderPaymentStatus,
)

logger = logging.getLogger(__name__)


class TossPaymentProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 502,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


class TossPaymentProvider:
    name = "toss"

    def __init__(
        self,
        *,
        secret_key: str,
        base_url: str,
        api_version: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.timeout_seconds = timeout_seconds

    def _pending_payment_id(self, order_id: UUID) -> str:
        return f"toss_order_{order_id.hex}"

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        if not self.secret_key:
            raise TossPaymentProviderError(
                "toss_secret_key_missing",
                "토스페이먼츠 시크릿 키가 설정되어 있지 않습니다.",
                status_code=500,
            )

        encoded = base64.b64encode(f"{self.secret_key}:".encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "TossPayments-Version": self.api_version,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _status_from_toss(self, status: str) -> ProviderPaymentStatus:
        if status in {"DONE", "PARTIAL_CANCELED"}:
            return ProviderPaymentStatus.APPROVED
        if status in {"CANCELED", "ABORTED", "EXPIRED"}:
            return ProviderPaymentStatus.CANCELLED
        if status in {"WAITING_FOR_DEPOSIT", "IN_PROGRESS", "READY"}:
            return ProviderPaymentStatus.PENDING
        return ProviderPaymentStatus.FAILED

    async def create_payment(self, order_id: UUID, amount: int) -> ProviderPayment:
        return ProviderPayment(
            id=self._pending_payment_id(order_id),
            order_id=order_id,
            amount=amount,
            status=ProviderPaymentStatus.PENDING,
        )

    async def confirm_payment(
        self,
        *,
        payment_key: str,
        order_id: UUID,
        amount: int,
        idempotency_key: str,
    ) -> ProviderEvent:
        logger.info(
            "Toss confirm requested: order_id=%s amount=%s idempotency_key=%s",
            order_id,
            amount,
            idempotency_key,
        )
        payload = {
            "paymentKey": payment_key,
            "orderId": str(order_id),
            "amount": amount,
        }
        data = await self._request(
            "POST",
            "/v1/payments/confirm",
            idempotency_key=idempotency_key,
            json=payload,
        )
        status = self._status_from_toss(str(data.get("status", "")))
        failure = data.get("failure") or {}
        logger.info(
            "Toss confirm response mapped: order_id=%s toss_status=%s provider_status=%s",
            order_id,
            data.get("status"),
            status.value,
        )
        return ProviderEvent(
            id=f"toss_confirm:{payment_key}:{status.value}",
            payment_id=payment_key,
            order_id=order_id,
            amount=amount,
            status=status,
            failure_code=failure.get("code"),
        )

    async def get_payment(self, payment_id: str) -> ProviderPayment | None:
        if payment_id.startswith("toss_order_"):
            return None

        data = await self._request("GET", f"/v1/payments/{payment_id}")
        order_id = self._parse_order_id(data.get("orderId"))
        if order_id is None:
            return None
        status = self._status_from_toss(str(data.get("status", "")))
        return ProviderPayment(
            id=payment_id,
            order_id=order_id,
            amount=int(data.get("totalAmount") or data.get("amount") or 0),
            status=status,
            terminal_event_id=f"toss_reconcile:{payment_id}:{status.value}",
            failure_code=(data.get("failure") or {}).get("code"),
        )

    async def cancel_payment(self, payment_id: str) -> ProviderPayment:
        if payment_id.startswith("toss_order_"):
            return ProviderPayment(
                id=payment_id,
                order_id=self._order_id_from_pending_payment_id(payment_id),
                amount=1,
                status=ProviderPaymentStatus.CANCELLED,
            )

        data = await self._request(
            "POST",
            f"/v1/payments/{payment_id}/cancel",
            idempotency_key=f"cancel:{payment_id}",
            json={"cancelReason": "사용자 요청으로 결제를 취소했습니다."},
        )
        order_id = self._parse_order_id(data.get("orderId"))
        if order_id is None:
            raise TossPaymentProviderError(
                "invalid_toss_payment_response",
                "토스페이먼츠 응답에서 주문 ID를 확인할 수 없습니다.",
            )
        return ProviderPayment(
            id=payment_id,
            order_id=order_id,
            amount=int(data.get("totalAmount") or data.get("amount") or 0),
            status=self._status_from_toss(str(data.get("status", ""))),
            terminal_event_id=f"toss_cancel:{payment_id}",
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        idempotency_key: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        logger.info("Toss API request: method=%s path=%s", method, path)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(idempotency_key),
                    json=json,
                )
        except httpx.HTTPError as error:
            logger.warning(
                "Toss API network error: method=%s path=%s error=%s",
                method,
                path,
                error,
            )
            raise TossPaymentProviderError(
                "toss_payment_provider_unavailable",
                "토스페이먼츠와 통신할 수 없습니다.",
            ) from error

        if response.status_code >= 400:
            try:
                data = response.json()
            except ValueError:
                data = {}
            logger.warning(
                "Toss API error response: method=%s path=%s status=%s code=%s message=%s",
                method,
                path,
                response.status_code,
                data.get("code"),
                data.get("message"),
            )
            raise TossPaymentProviderError(
                str(data.get("code") or "toss_payment_provider_error"),
                str(data.get("message") or "토스페이먼츠 요청이 실패했습니다."),
                status_code=502,
                payload=data,
            )

        logger.info(
            "Toss API success response: method=%s path=%s status=%s",
            method,
            path,
            response.status_code,
        )
        return response.json()

    def _parse_order_id(self, value: Any) -> UUID | None:
        if not isinstance(value, str):
            return None
        try:
            return UUID(value)
        except ValueError:
            return None

    def _order_id_from_pending_payment_id(self, payment_id: str) -> UUID:
        return UUID(payment_id.removeprefix("toss_order_"))
