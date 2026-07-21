from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.auth import InvalidCredentialsError
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
