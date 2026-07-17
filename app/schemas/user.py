from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, SecretStr


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: SecretStr

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
