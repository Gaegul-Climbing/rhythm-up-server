from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.web.router import WEB_ROOT
from app.web.router import router as web_router


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime_settings()
    application = FastAPI(
        title="리듬업 연습실 API",
        version="0.1.0",
        description="프랜차이즈 공유 연습실 예약 서비스",
        lifespan=lifespan,
    )
    register_exception_handlers(application)
    application.include_router(api_router)
    application.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")
    application.include_router(web_router)
    return application


app = create_app()
