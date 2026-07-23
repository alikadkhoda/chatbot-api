from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
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

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials(
        request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid email or password"},
        )

    @app.exception_handler(InvalidTokenError)
    async def invalid_token(request: Request, exc: InvalidTokenError) -> JSONResponse:
        return JSONResponse(
            status_code=401, content={"detail": "Invalid or expired token."}
        )

    @app.exception_handler(InactiveUserError)
    async def inactive_user(request: Request, exc: InactiveUserError) -> JSONResponse:
        return JSONResponse(
            status_code=403, content={"detail": "User account is inactive"}
        )
