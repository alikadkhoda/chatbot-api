from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {
        "message": "Hello, ChatBot API!"
    }

@app.get("/health")
async def health():
    return {
        "status": "ok"
    }

@app.get("/version")
async def version():
    return {
        "version": "0.1.0"
    }