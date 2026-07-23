from fastapi import APIRouter, Depends

from app.dependencies.services import get_auth_service
from app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest, service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    return await service.authenticate(data=data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    return await service.refresh_access_token(data.refresh_token)


@router.post("/logout")
async def logout(
    data: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)
) -> dict[str, str]:
    await service.logout(data.refresh_token)

    return {"detail": "Logged out successfully."}
