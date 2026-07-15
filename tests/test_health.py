from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.api.routes import health


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_liveness_does_not_check_external_dependencies(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_available_dependencies(
    client: AsyncClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(health, "_check_database", AsyncMock(return_value=True))
    monkeypatch.setattr(health, "_check_redis", AsyncMock(return_value=True))

    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok"},
    }


async def test_readiness_returns_service_unavailable_when_database_is_down(
    client: AsyncClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(health, "_check_database", AsyncMock(return_value=False))
    monkeypatch.setattr(health, "_check_redis", AsyncMock(return_value=True))

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": "unavailable", "redis": "ok"},
    }
