from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import router as auth_router
from app.api.v1.chats import router as chats_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.messages import router as messages_router
from app.api.v1.users import router as users_router
from app.core.config import settings
from app.database.redis import close_redis_client, create_redis_client
from app.database.session import get_session
from app.exceptions.handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = create_redis_client()
    app.state.redis = redis

    try:
        yield
    finally:
        await close_redis_client(redis)


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": "0.1.0"}


@app.get("/db-test")
async def db_test(session: AsyncSession = Depends(get_session)):
    ping = await session.execute(text("SELECT 1;"))
    db_name = await session.execute(text("SELECT current_database();"))

    return {"ping": ping.scalar(), "database": db_name.scalar()}


register_exception_handlers(app)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(messages_router)
app.include_router(conversation_router)
