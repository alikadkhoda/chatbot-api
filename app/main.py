from fastapi import FastAPI

from app.core.config import settings

app = FastAPI()


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
