class AppException(Exception):
    """Base exception for application-level errors."""

    status_code: int = 500
    code: str = "INTERNAL_SERVER_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
    ) -> None:
        self.message = message or self.message
        super().__init__(self.message)
