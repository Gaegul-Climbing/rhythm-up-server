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
