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
from app.services.conversation_context import ConversationContextBuilder
from app.services.conversation_summary import ConversationSummaryService
from app.services.message import MessageService
from app.services.user import UserService
from app.tools.bank_card_validator import BankCardValidatorTool
from app.tools.registry import ToolRegistry


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


def get_tool_registry() -> ToolRegistry:
    return ToolRegistry([BankCardValidatorTool()])


def get_conversation_context_builder() -> ConversationContextBuilder:
    return ConversationContextBuilder(
        max_tokens=settings.ai.context_window,
        reserve_tokens=settings.ai.reserve_tokens,
        summary_trigger_tokens=settings.ai.summary_trigger_tokens,
    )


def get_conversation_service(
    chat_service: ChatService = Depends(get_chat_service),
    message_service: MessageService = Depends(get_message_service),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    context_builder: ConversationContextBuilder = Depends(
        get_conversation_context_builder
    ),
) -> ConversationOrchestratorService:
    provider = LLMProviderFactory.create(settings=settings.ai)
    summary_service = ConversationSummaryService(provider=provider)

    return ConversationOrchestratorService(
        chat_service=chat_service,
        message_service=message_service,
        provider=provider,
        tool_registry=tool_registry,
        context_builder=context_builder,
        summary_service=summary_service,
        system_prompt=settings.ai.system_prompt,
    )
