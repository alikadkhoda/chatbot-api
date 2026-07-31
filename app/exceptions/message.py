from app.exceptions.base import AppException


class MessageNotFoundError(AppException):
    status_code = 404
    code = "MESSAGE_NOT_FOUND"
    message = "Message not found."


class MessageImmutableError(AppException):
    status_code = 409
    code = "MESSAGE_IMMUTABLE"
    message = "This message cannot be modified"
