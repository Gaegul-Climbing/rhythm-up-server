import logging

from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.errors import ApplicationError
from app.main import create_app


async def test_application_error_uses_common_response_format() -> None:
    application = create_app()
    router = APIRouter()

    @router.get("/test-error")
    async def raise_test_error() -> None:
        raise ApplicationError(
            code="test_error",
            message="테스트 오류입니다.",
            status_code=409,
        )

    application.include_router(router)

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "test_error",
            "message": "테스트 오류입니다.",
        }
    }


async def test_not_found_uses_common_response_format() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Not Found",
        }
    }


async def test_validation_errors_do_not_echo_or_log_input_values(caplog) -> None:
    secret = "do-not-log-this-password"
    transport = ASGITransport(app=create_app())

    with caplog.at_level(logging.WARNING):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/auth/signup",
                json={
                    "email": "invalid-email",
                    "password": secret,
                    "name": "테스트",
                    "phone": "010-1234-5678",
                },
            )

    assert response.status_code == 422
    assert secret not in response.text
    assert secret not in caplog.text
    details = response.json()["error"]["details"]
    assert all("input" not in detail for detail in details)
