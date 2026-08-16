from app.exceptions.base import AppException


class ToolNotFoundError(AppException):
    status_code = 500
    code = "TOOL_NOT_FOUND"
    message = "The requested tool is not registered."


class ToolExecutionError(AppException):
    status_code = 500
    code = "TOOL_EXECUTION_ERROR"
    message = "Failed to execute the requested tool."


class ToolLoopLimitError(AppException):
    status_code = 500
    code = "TOOL_LOOP_LIMIT_EXCEEDED"
    message = "The maximum number of tool iterations was exceeded."
