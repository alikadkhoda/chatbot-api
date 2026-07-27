from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChatRead(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
