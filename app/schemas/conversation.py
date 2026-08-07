from pydantic import BaseModel


class ConversationRequest(BaseModel):
    content: str
