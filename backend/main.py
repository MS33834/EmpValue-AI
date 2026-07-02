"""
FastAPI 应用入口
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.deps import AppState
from api.auth_routes import router as auth_router
from api.routes import router
from core.config import get_settings
from core.database import close_db, init_db
from core.metrics import setup_metrics
from core.tracing import tracer


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    app.state.app_state = AppState(settings)
    try:
        yield
    finally:
        await app.state.app_state.close()
        try:
            tracer.close()
        except Exception:
            pass
        await close_db()


class LimitRequestBodyMiddleware(BaseHTTPMiddleware):
    """限制请求体大小，防止超大 JSON/Base64 附件导致内存耗尽。"""

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
            except ValueError:
                length = 0
            if length > self.MAX_CONTENT_LENGTH:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=413,
                    content={"detail": "请求体超过 10MB 限制"},
                )
        return await call_next(request)


app = FastAPI(
    title="EmpValue-AI",
    description="AI 驱动员工价值量化与成长 Agent 系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(LimitRequestBodyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Trace-Id"],
)

app.include_router(auth_router)
app.include_router(router)

# 挂载 Prometheus 指标端点（/metrics，无需鉴权，供 Prometheus 抓取）
setup_metrics(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
