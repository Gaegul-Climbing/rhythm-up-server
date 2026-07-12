import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ApplicationError

logger = logging.getLogger(__name__)


def safe_validation_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "loc": item.get("loc", ()),
            "type": item.get("type", "validation_error"),
            "msg": item.get("msg", "요청 값이 올바르지 않습니다."),
        }
        for item in errors
    ]


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details is not None:
        body["error"]["details"] = jsonable_encoder(details)

    return JSONResponse(status_code=status_code, content=body, headers=headers)


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exception: ApplicationError,
    ) -> JSONResponse:
        logger.warning(
            "Application error: method=%s path=%s status=%s code=%s",
            request.method,
            request.url.path,
            exception.status_code,
            exception.code,
        )
        return error_response(
            status_code=exception.status_code,
            code=exception.code,
            message=exception.message,
            details=exception.details,
            headers=exception.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        details = safe_validation_details(exception.errors())
        logger.warning(
            "Validation error: method=%s path=%s errors=%s",
            request.method,
            request.url.path,
            details,
        )
        return error_response(
            status_code=422,
            code="validation_error",
            message="요청 값이 올바르지 않습니다.",
            details=details,
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request,
        exception: StarletteHTTPException,
    ) -> JSONResponse:
        message = exception.detail if isinstance(exception.detail, str) else "요청이 실패했습니다."
        details = None if isinstance(exception.detail, str) else exception.detail
        logger.warning(
            "HTTP error: method=%s path=%s status=%s detail=%s has_authorization=%s",
            request.method,
            request.url.path,
            exception.status_code,
            exception.detail,
            bool(request.headers.get("authorization")),
        )
        return error_response(
            status_code=exception.status_code,
            code="http_error",
            message=message,
            details=details,
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(
        _request: Request,
        exception: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled application error", exc_info=exception)
        return error_response(
            status_code=500,
            code="internal_server_error",
            message="서버 내부 오류가 발생했습니다.",
        )
