from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_active_user
from app.dependencies.services import get_message_service
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRead, MessageUpdate
from app.services.message import MessageService

router = APIRouter(prefix="/chats/{chat_id}/messages", tags=["Messages"])


@router.post("", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message(
    chat_id: UUID,
    data: MessageCreate,
    service: MessageService = Depends(get_message_service),
    current_user: User = Depends(get_current_active_user),
) -> MessageRead:
    return await service.create_message(
        chat_id=chat_id, user_id=current_user.id, data=data
    )


@router.get("", response_model=list[MessageRead])
async def get_messages(
    chat_id: UUID,
    service: MessageService = Depends(get_message_service),
    current_user: User = Depends(get_current_active_user),
) -> list[MessageRead]:
    return await service.get_messages(chat_id=chat_id, user_id=current_user.id)


@router.get("/{message_id}", response_model=MessageRead)
async def get_message(
    chat_id: UUID,
    message_id: UUID,
    service: MessageService = Depends(get_message_service),
    current_user: User = Depends(get_current_active_user),
) -> MessageRead:
    return await service.get_message(
        chat_id=chat_id, message_id=message_id, user_id=current_user.id
    )


@router.patch("/{message_id}", response_model=MessageRead)
async def update_message(
    chat_id: UUID,
    message_id: UUID,
    data: MessageUpdate,
    service: MessageService = Depends(get_message_service),
    current_user: User = Depends(get_current_active_user),
) -> MessageRead:
    return await service.update_message(
        chat_id=chat_id, message_id=message_id, user_id=current_user.id, data=data
    )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    chat_id: UUID,
    message_id: UUID,
    service: MessageService = Depends(get_message_service),
    current_user: User = Depends(get_current_active_user),
) -> None:
    await service.delete_message(
        chat_id=chat_id, message_id=message_id, user_id=current_user.id
    )
