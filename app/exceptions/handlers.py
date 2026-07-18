from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.user import EmailAlreadyExistsError


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(EmailAlreadyExistsError)
    async def email_exists(
        request: Request, exc: EmailAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Email already exists."},
        )
