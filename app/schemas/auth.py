from pydantic import BaseModel, ConfigDict, EmailStr, SecretStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
