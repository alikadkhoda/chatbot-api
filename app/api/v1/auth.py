from fastapi import APIRouter, Depends

from app.dependencies.services import get_auth_service
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest, service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    return await service.authenticate(data=data)
