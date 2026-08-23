from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tool import ToolCall, ToolDefinition


class LLMMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class LLMMessage(BaseModel):
    role: LLMMessageRole
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_name: str | None = None
    tool_call_id: str | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    content: str | None = Field(min_length=1)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: LLMUsage | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LLMRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1)
    model: str | None = None
    tools: list[ToolDefinition] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LLMStreamChunk(BaseModel):
    content: str | None = None
    usage: LLMUsage | None = None
