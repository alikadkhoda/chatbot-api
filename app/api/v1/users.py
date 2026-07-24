from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_active_user
from app.dependencies.services import get_user_service
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
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


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user),
) -> UserRead:
    return await service.get_user_for_current_user(
        target_user_id=user_id, current_user=current_user
    )


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user),
) -> UserRead:
    return await service.update_user(
        target_user_id=user_id, data=data, current_user=current_user
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user),
) -> None:
    await service.delete_user(target_user_id=user_id, current_user=current_user)
