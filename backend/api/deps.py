"""
FastAPI 依赖注入
"""

from typing import AsyncGenerator

from fastapi import Request

from agent.graph import create_evaluation_graph
from agent.prompt_loader import PromptLoader
from agent.tools import AgentToolkit, DummyCompanyKB, DummyMemoryStore
from core.config import Settings, get_settings
from core.model_router import ModelRouter
from services.approval_service import ApprovalService
from services.audit_service import AuditService


class AppState:
    """应用级共享状态"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_router = ModelRouter(settings)
        self.prompt_loader = PromptLoader()
        self.toolkit = AgentToolkit(
            memory=DummyMemoryStore(),
            kb=DummyCompanyKB(),
        )
        self.approval_service = ApprovalService()
        self.audit_service = AuditService()

    def get_graph(self):
        return create_evaluation_graph(
            toolkit=self.toolkit,
            model_router=self.model_router,
            prompt_loader=self.prompt_loader,
        )


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


def get_settings_dep() -> Settings:
    return get_settings()
