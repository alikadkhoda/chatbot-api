from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.base import AppException
from app.schemas.error import ErrorDetail, ErrorResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        error_detail = ErrorDetail(
            code=exc.code,
            message=exc.message,
        )

        error_response = ErrorResponse(
            error=error_detail,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
        )
