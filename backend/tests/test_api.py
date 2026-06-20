"""
FastAPI API 测试
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent.graph import create_evaluation_graph
from agent.prompt_loader import PromptLoader
from agent.tools import AgentToolkit, DummyCompanyKB, DummyMemoryStore
from api.deps import AppState
from auth.rbac import Role
from core.config import Settings
from core.model_router import ModelRouter
from main import app
from schemas import EmployeeEvaluation

from .test_graph import MockModelRouter, build_sample_llm_response


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_app_state(client):
    """注入 Mock 后的 AppState，避免真实 LLM 调用"""
    settings = Settings(model_tier="L0")
    state = AppState(settings)

    # 使用测试 Prompt
    prompt_dir = state.prompt_loader.prompts_dir

    # 注入 Mock Graph
    response = build_sample_llm_response()
    state.get_graph = lambda: create_evaluation_graph(
        toolkit=AgentToolkit(DummyMemoryStore(), DummyCompanyKB()),
        model_router=MockModelRouter(response),
        prompt_loader=PromptLoader(prompt_dir),
    )
    client.app.state.app_state = state
    return state


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_model_status_admin(client, mock_app_state):
    with patch("auth.rbac.get_current_user_role", return_value=Role.ADMIN):
        resp = client.get("/api/v1/admin/model-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended_tier" in data


def test_create_evaluation(client, mock_app_state):
    payload = {
        "employee_id": "E1001",
        "period": "2026-W25",
        "raw_inputs": [
            {"input_id": "daily-001", "content": "完成了登录模块重构"},
        ],
    }
    resp = client.post("/api/v1/evaluations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["evaluation"]["employee_id"] == "E1001"


def test_approve_evaluation(client, mock_app_state):
    resp = client.post(
        "/api/v1/evaluations/EV-001/approve",
        json={"current_status": "ai_drafted", "actor_id": "M001", "comment": "同意"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"


def test_reject_illegal_transition(client, mock_app_state):
    resp = client.post(
        "/api/v1/evaluations/EV-001/approve",
        json={"current_status": "approved", "actor_id": "M001"},
    )
    assert resp.status_code == 400


def test_get_evaluation_audit_logs(client, mock_app_state):
    # 先产生一条审批记录
    client.post(
        "/api/v1/evaluations/EV-001/approve",
        json={"current_status": "ai_drafted", "actor_id": "M001"},
    )
    resp = client.get("/api/v1/evaluations/EV-001/audit-logs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["logs"]) >= 1
