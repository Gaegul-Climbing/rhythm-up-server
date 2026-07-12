import pytest

from app.core.config import DEVELOPMENT_JWT_SECRET, Settings


def test_settings_have_local_service_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.redis_url.startswith("redis://")


def test_production_rejects_default_jwt_secret() -> None:
    settings = Settings(_env_file=None, app_env="production", jwt_secret_key=DEVELOPMENT_JWT_SECRET)

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        settings.validate_runtime_settings()


def test_production_accepts_strong_jwt_secret() -> None:
    settings = Settings(_env_file=None, app_env="production", jwt_secret_key="a" * 32)

    settings.validate_runtime_settings()
