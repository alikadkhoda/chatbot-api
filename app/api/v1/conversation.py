from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_active_user
from app.dependencies.services import get_conversation_service
from app.models.user import User
from app.schemas.conversation import ConversationRequest
from app.schemas.message import MessageRead
from app.services.conversation import ConversationOrchestratorService

router = APIRouter(prefix="/chats", tags=["Conversation"])


@router.post(
    "/{chat_id}/ai", response_model=MessageRead, status_code=status.HTTP_201_CREATED
)
async def send_message(
    chat_id: UUID,
    data: ConversationRequest,
    current_user: User = Depends(get_current_active_user),
    service: ConversationOrchestratorService = Depends(get_conversation_service),
) -> MessageRead:
    return await service.send_message(
        chat_id=chat_id, user_id=current_user.id, content=data.content
    )
