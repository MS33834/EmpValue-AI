"""
FastAPI 应用入口
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.deps import AppState
from api.routes import router
from core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.app_state = AppState(settings)
    yield


app = FastAPI(
    title="EmpValue-AI",
    description="AI 驱动员工价值量化与成长 Agent 系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
