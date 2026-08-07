from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_session
from app.providers.factory import LLMProviderFactory
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.chat import ChatService
from app.services.conversation import ConversationOrchestratorService
from app.services.message import MessageService
from app.services.user import UserService


def get_user_service(
    session: AsyncSession = Depends(get_session),
) -> UserService:
    repository = UserRepository(session)

    return UserService(repository)


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    user_repository = UserRepository(session=session)
    refresh_token_repository = RefreshTokenRepository(session=session)

    return AuthService(
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
    )


def get_chat_service(session: AsyncSession = Depends(get_session)) -> ChatService:
    repository = ChatRepository(session=session)

    return ChatService(repository=repository)


def get_message_service(session: AsyncSession = Depends(get_session)) -> MessageService:
    message_repository = MessageRepository(session=session)
    chat_repository = ChatRepository(session=session)

    return MessageService(
        message_repository=message_repository, chat_repository=chat_repository
    )


def get_conversation_service(
    chat_service: ChatService = Depends(get_chat_service),
    message_service: MessageService = Depends(get_message_service),
) -> ConversationOrchestratorService:
    provider = LLMProviderFactory.create(settings=settings.ai)

    return ConversationOrchestratorService(
        chat_service=chat_service, message_service=message_service, provider=provider
    )
