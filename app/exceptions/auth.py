from app.exceptions.base import AppException


class AuthenticationError(AppException):
    """Base exception for authentication failures."""

    status_code = 401
    code = "AUTHENTICATION_ERROR"
    message = "Authentication failed."


class InvalidCredentialsError(AuthenticationError):
    code = "INVALID_CREDENTIALS"
    message = "Invalid email or password."


class InvalidTokenError(AuthenticationError):
    code = "INVALID_TOKEN"
    message = "Invalid or expired token."


class InactiveUserError(AuthenticationError):
    code = "INACTIVE_USER"
    message = "User account is inactive."


class AuthorizationError(AppException):
    """Base exception for authorization failures."""

    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."
