from typing import Any, Protocol

from app.schemas.tool import ToolDefinition, ToolResult


class Tool(Protocol):
    @property
    def definition(self) -> ToolDefinition: ...

    async def execute(self, arguments: dict[str, Any]) -> ToolResult: ...
