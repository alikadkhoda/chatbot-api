from pydantic import BaseModel, ConfigDict, Field


class CardValidationArguments(BaseModel):
    card_number: str = Field(min_length=16, max_length=16, pattern=r"^\d{16}$")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CardValidationResult(BaseModel):
    valid: bool

    model_config = ConfigDict(extra="forbid")
