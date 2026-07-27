from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_active_user
from app.dependencies.services import get_chat_service
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatRead, ChatUpdate
from app.services.chat import ChatService

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.post("", response_model=ChatRead, status_code=status.HTTP_201_CREATED)
async def create_chat(
    data: ChatCreate,
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> ChatRead:
    return await service.create_chat(data=data, user_id=current_user.id)


@router.get("", response_model=list[ChatRead])
async def get_chats(
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> list[ChatRead]:
    return await service.get_chats(user_id=current_user.id)


@router.get("/{chat_id}", response_model=ChatRead)
async def get_chat(
    chat_id: UUID,
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> ChatRead:
    return await service.get_chat(chat_id=chat_id, user_id=current_user.id)


@router.patch("/{chat_id}")
async def update_chat(
    chat_id: UUID,
    data: ChatUpdate,
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> ChatRead:
    return await service.chat_update(
        chat_id=chat_id, data=data, user_id=current_user.id
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: UUID,
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> None:
    await service.delete_chat(chat_id=chat_id, user_id=current_user.id)
