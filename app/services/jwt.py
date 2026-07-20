from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=settings.access_token_expire_minutes,
    )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload=payload,
        key=settings.secret_key,
        algorithm=settings.algorithm,
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        jwt=token,
        key=settings.secret_key,
        algorithms=[settings.algorithm],
    )
