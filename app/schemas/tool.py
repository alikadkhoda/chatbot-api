from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    parameters: dict[str, Any]

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ToolCall(BaseModel):
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any]

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ToolResult(BaseModel):
    content: str = Field(min_length=1)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )
