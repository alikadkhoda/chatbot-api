from app.exceptions.base import AppException


class MessageNotFoundError(AppException):
    status_code = 404
    code = "MESSAGE_NOT_FOUND"
    message = "Message not found."
