from app.exceptions.base import AppException


class ConversationError(AppException):
    status_code = 500
    code = "CONVERSATION_ERROR"
    message = "Failed to process the conversation."


class ConversationContextError(ConversationError):
    code = "CONVERSATION_CONTEXT_ERROR"
    message = "Failed to build the conversation context."


class ConversationStreamError(ConversationError):
    status_code = 502
    code = "CONVERSATION_STREAM_ERROR"
    message = "The AI response stream was interrupted."
