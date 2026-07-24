from app.exceptions.base import AppException


class EmailAlreadyExistsError(AppException):
    status_code = 409
    code = "EMAIL_ALREADY_EXISTS"
    message = "Email already exists."
