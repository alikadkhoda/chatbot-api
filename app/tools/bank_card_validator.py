from typing import Any

from app.schemas.bank import CardValidationArguments
from app.schemas.tool import ToolDefinition, ToolResult


class BankCardValidatorTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="validate_bank_card",
            description=" Validate an bank card number using the Luhn algorithm",
            parameters={
                "type": "object",
                "properties": {
                    "card_number": {
                        "type": "string",
                        "description": "A 16-digit Iranian bank card number",
                    },
                },
                "required": ["card_number"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        args = CardValidationArguments.model_validate(arguments)

        valid = self._is_valid(args.card_number)

        return ToolResult(
            content=(
                "The bank card number is valid."
                if valid
                else "The bank card number is invalid."
            )
        )

    def _is_valid(self, card_number: str) -> bool:
        total = 0

        for index, digit in enumerate(map(int, reversed(card_number))):
            if index % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9

            total += digit

        return total % 10 == 0
