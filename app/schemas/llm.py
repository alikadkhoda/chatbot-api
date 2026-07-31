from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LLMMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class LLMMessage(BaseModel):
    role: LLMMessageRole
    content: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LLMResponse(BaseModel):
    content: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LLMRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1)
    model: str | None = None

    model_config = ConfigDict(extra="forbid")
