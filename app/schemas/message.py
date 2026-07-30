from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.message import MessageRole


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MessageRead(BaseModel):
    id: UUID
    chat_id: UUID
    role: MessageRole
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=100_000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
