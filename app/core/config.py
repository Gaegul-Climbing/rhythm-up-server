from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://practice:practice@localhost:5432/practice"
    database_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "local-development-secret-change-me"
    jwt_access_token_expire_minutes: int = 30
    business_timezone: str = "Asia/Seoul"
    reservation_hold_ttl_seconds: int = 300
    redis_key_prefix: str = "practice-server"
    payment_provider: str = "local"
    local_payment_state_ttl_seconds: int = 86400
    toss_payments_client_key: str = ""
    toss_payments_secret_key: str = ""
    toss_payments_base_url: str = "https://api.tosspayments.com"
    toss_payments_api_version: str = "2024-06-01"
    toss_payments_success_url: str = "http://localhost:8000/?paymentResult=success"
    toss_payments_fail_url: str = "http://localhost:8000/?paymentResult=fail"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
