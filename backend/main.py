"""
FastAPI 应用入口
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import AppState
from api.auth_routes import router as auth_router
from api.routes import router
from core.config import get_settings
from core.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    app.state.app_state = AppState(settings)
    yield
    await close_db()


app = FastAPI(
    title="EmpValue-AI",
    description="AI 驱动员工价值量化与成长 Agent 系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Trace-Id"],
)

app.include_router(auth_router)
app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
