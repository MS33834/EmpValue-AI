"""
FastAPI API 测试
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agent.graph import create_evaluation_graph
from agent.prompt_loader import PromptLoader
from agent.tools import AgentToolkit, DummyCompanyKB, DummyMemoryStore
from api.deps import AppState
from auth.rbac import Role
from core.config import Settings, get_settings
from core.database import close_db, init_db
from main import app

from .test_graph import MockModelRouter, build_sample_llm_response


@pytest.fixture(autouse=True)
def temp_database(monkeypatch):
    """每个测试使用独立临时 SQLite 数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_url = f"sqlite+aiosqlite:///{tmp.name}"

    monkeypatch.setattr(get_settings(), "database_url", db_url)

    # 重新创建 engine（因为 core.database 在导入时已创建原 engine）
    from core import database as db_module

    db_module.engine = db_module.create_async_engine(
        db_url,
        echo=False,
        future=True,
    )
    db_module.AsyncSessionLocal = db_module.async_sessionmaker(
        bind=db_module.engine,
        class_=db_module.AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    yield

    # 清理
    try:
        Path(tmp.name).unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
async def initialized_db(temp_database):
    await init_db()
    yield
    await close_db()


@pytest.fixture
def client(initialized_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_app_state(client):
    """注入 Mock 后的 AppState，避免真实 LLM 调用"""
    settings = Settings(model_tier="L0")
    state = AppState(settings)

    prompt_dir = state.prompt_loader.prompts_dir
    response = build_sample_llm_response()

    state.get_graph = lambda eval_service: create_evaluation_graph(
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


@pytest.fixture
def created_evaluation_id(client, mock_app_state):
    """通过 API 创建一条评估并返回 evaluation_id"""
    payload = {
        "employee_id": "E1001",
        "period": "2026-W25",
        "raw_inputs": [
            {"input_id": "daily-001", "content": "完成了登录模块重构"},
        ],
    }
    resp = client.post("/api/v1/evaluations", json=payload)
    assert resp.status_code == 200
    return resp.json()["evaluation"]["evaluation_id"]


def test_approve_evaluation(client, mock_app_state, created_evaluation_id):
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "ai_drafted", "actor_id": "M001", "comment": "同意"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"


def test_reject_illegal_transition(client, mock_app_state, created_evaluation_id):
    # 先审批通过
    client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "ai_drafted", "actor_id": "M001"},
    )
    # 再次 approve 已 approved 的状态应返回 400
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "approved", "actor_id": "M001"},
    )
    assert resp.status_code == 400


def test_get_evaluation_audit_logs(client, mock_app_state, created_evaluation_id):
    client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "ai_drafted", "actor_id": "M001"},
    )
    resp = client.get(f"/api/v1/evaluations/{created_evaluation_id}/audit-logs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["logs"]) >= 1


def test_get_evaluation_detail(client, mock_app_state, created_evaluation_id):
    resp = client.get(f"/api/v1/evaluations/{created_evaluation_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert "employee_view" in data
    assert "manager_view" in data


def test_get_evaluation_employee_view(client, mock_app_state, created_evaluation_id):
    resp = client.get(f"/api/v1/evaluations/{created_evaluation_id}/employee-view")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert "summary" in data["employee_view"]
    assert "growth_areas" in data["employee_view"]


def test_get_evaluation_manager_view(client, mock_app_state, created_evaluation_id):
    resp = client.get(f"/api/v1/evaluations/{created_evaluation_id}/manager-view")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert "harsh_assessment" in data["manager_view"]


def test_create_evaluation_feedback(client, mock_app_state, created_evaluation_id):
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/feedback",
        json={"content": "我认为评估中关于协作的部分可以更具体", "type": "feedback", "actor_id": "E1001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert data["content"]


def test_get_employee_dashboard(client, mock_app_state, created_evaluation_id):
    resp = client.get("/api/v1/employees/E1001/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["employee_id"] == "E1001"


def test_create_input(client, mock_app_state):
    payload = {
        "employee_id": "E1002",
        "period": "2026-W25",
        "type": "daily_report",
        "content": "本周完成了用户管理模块开发",
    }
    resp = client.post("/api/v1/inputs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["employee_id"] == "E1002"
    assert data["input_id"].startswith("input-")
