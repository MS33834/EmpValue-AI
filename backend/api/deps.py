"""
FastAPI 依赖注入
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agent.graph import create_evaluation_graph
from agent.prompt_loader import PromptLoader
from agent.tools import AgentToolkit
from core.config import Settings, get_settings
from core.database import get_db
from core.model_router import ModelRouter
from memory.vector_store import ChromaCompanyKB, ChromaMemoryStore
from services.approval_service import ApprovalService
from services.audit_service import AuditService
from services.evaluation_service import EvaluationService


class AppState:
    """应用级共享状态（无请求级数据库会话）"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_router = ModelRouter(settings)
        self.prompt_loader = PromptLoader()
        self.memory_store = ChromaMemoryStore(settings=settings)
        self.company_kb = ChromaCompanyKB(settings=settings)

    def get_graph(self, eval_service: EvaluationService):
        """创建并返回一个与当前数据库会话绑定的 LangGraph 实例"""
        toolkit = AgentToolkit(
            memory=self.memory_store,
            kb=self.company_kb,
        )
        return create_evaluation_graph(
            toolkit=toolkit,
            model_router=self.model_router,
            prompt_loader=self.prompt_loader,
        )


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


def get_settings_dep() -> Settings:
    return get_settings()


def get_approval_service(session: AsyncSession = Depends(get_db)) -> ApprovalService:
    return ApprovalService(session)


def get_audit_service(session: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(session)


def get_evaluation_service(session: AsyncSession = Depends(get_db)) -> EvaluationService:
    return EvaluationService(session)
