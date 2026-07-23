from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_active_user
from app.dependencies.services import get_user_service
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/register", response_model=UserRead)
async def register(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserRead:
    return await service.create_user(data)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_active_user)) -> UserRead:
    return UserRead.model_validate(current_user)
