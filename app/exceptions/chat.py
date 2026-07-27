from app.exceptions.base import AppException


class ChatNotFoundError(AppException):
    status_code = 404
    code = "CHAT_NOT_FOUND"
    message = "Chat not found."
