"""
FastAPI API 测试
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agent.graph import create_evaluation_graph, create_evaluation_graph_with_interrupt
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
def mock_app_state(client, temp_vector_store):
    """注入 Mock 后的 AppState，避免真实 LLM 调用"""
    settings = Settings(model_tier="L0")
    settings.vector_store_dir = temp_vector_store
    state = AppState(settings)

    prompt_dir = state.prompt_loader.prompts_dir
    response = build_sample_llm_response()

    state.memory_store = DummyMemoryStore()
    state.company_kb = DummyCompanyKB()
    mock_toolkit = AgentToolkit(DummyMemoryStore(), DummyCompanyKB())
    mock_router = MockModelRouter(response)
    mock_prompt_loader = PromptLoader(prompt_dir)

    state.get_graph = lambda eval_service: create_evaluation_graph(
        toolkit=mock_toolkit,
        model_router=mock_router,
        prompt_loader=mock_prompt_loader,
    )
    # 预创建带 interrupt 的图（使用 mock router），供 interrupt 接口测试使用
    state._interrupt_graph = create_evaluation_graph_with_interrupt(
        toolkit=mock_toolkit,
        model_router=mock_router,
        prompt_loader=mock_prompt_loader,
    )
    client.app.state.app_state = state
    return state


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_model_status_admin(client, mock_app_state):
    resp = client.get("/api/v1/admin/model-status", headers={"x-user-role": "admin"})
    assert resp.status_code == 200
    data = resp.json()
    assert "recommended_tier" in data


def _wait_for_job(client, job_id: str, timeout: float = 10.0) -> dict:
    """轮询异步评估任务，直到完成或超时"""
    import time

    start = time.time()
    while time.time() - start < timeout:
        resp = client.get(f"/api/v1/evaluations/jobs/{job_id}")
        assert resp.status_code == 200
        job = resp.json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.2)
    raise TimeoutError(f"任务 {job_id} 未在 {timeout}s 内完成")


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
    assert data["status"] == "pending"
    assert "job_id" in data

    job = _wait_for_job(client, data["job_id"])
    assert job["status"] == "completed"
    assert job["evaluation"]["employee_id"] == "E1001"


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
    job = _wait_for_job(client, resp.json()["job_id"])
    assert job["status"] == "completed"
    return job["evaluation"]["evaluation_id"]


def test_approve_evaluation(client, mock_app_state, created_evaluation_id):
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "manager_review", "actor_id": "M001", "comment": "同意"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"


def test_reject_illegal_transition(client, mock_app_state, created_evaluation_id):
    # 先审批通过
    client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "manager_review", "actor_id": "M001"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    # 再次 approve 已 approved 的状态应返回 400
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "approved", "actor_id": "M001"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    assert resp.status_code == 400


def test_get_evaluation_audit_logs(client, mock_app_state, created_evaluation_id):
    client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "ai_drafted", "actor_id": "M001"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    resp = client.get(
        f"/api/v1/evaluations/{created_evaluation_id}/audit-logs",
        headers={"x-user-role": "manager"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["logs"]) >= 1


def test_get_evaluation_detail(client, mock_app_state, created_evaluation_id):
    resp = client.get(
        f"/api/v1/evaluations/{created_evaluation_id}",
        headers={"x-user-role": "manager"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert "employee_view" in data
    assert "manager_view" in data


def test_get_evaluation_employee_view(client, mock_app_state, created_evaluation_id):
    resp = client.get(
        f"/api/v1/evaluations/{created_evaluation_id}/employee-view",
        headers={"x-user-id": "E1001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert "summary" in data["employee_view"]
    assert "growth_areas" in data["employee_view"]


def test_get_evaluation_manager_view(client, mock_app_state, created_evaluation_id):
    resp = client.get(
        f"/api/v1/evaluations/{created_evaluation_id}/manager-view",
        headers={"x-user-role": "manager"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert "harsh_assessment" in data["manager_view"]


def test_create_evaluation_feedback(client, mock_app_state, created_evaluation_id):
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/feedback",
        json={"content": "我认为评估中关于协作的部分可以更具体", "type": "feedback", "actor_id": "E1001"},
        headers={"x-user-id": "E1001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert data["content"]


def test_get_pending_approvals(client, mock_app_state, created_evaluation_id):
    resp = client.get(
        "/api/v1/manager/pending-approvals",
        headers={"x-user-role": "manager"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(e["evaluation_id"] == created_evaluation_id for e in data["pending"])


def test_request_hr_review(client, mock_app_state, created_evaluation_id):
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/request-hr-review",
        json={"current_status": "manager_review", "actor_id": "M001", "comment": "分数异常需复核"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "hr_audit"


def test_get_hr_audit_queue(client, mock_app_state, created_evaluation_id):
    # 先把评估送进 HR 复核
    client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/request-hr-review",
        json={"current_status": "manager_review", "actor_id": "M001"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    resp = client.get("/api/v1/hr/audit-queue", headers={"x-user-role": "hr"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(e["evaluation_id"] == created_evaluation_id for e in data["pending"])


def test_appeal_evaluation(client, mock_app_state, created_evaluation_id):
    # 先审批通过再申诉
    client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/approve",
        json={"current_status": "manager_review", "actor_id": "M001"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/appeal",
        json={"current_status": "approved", "actor_id": "E1001", "comment": "对评分有异议"},
        headers={"x-user-id": "E1001"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "manager_review"


def test_re_evaluate(client, mock_app_state, created_evaluation_id):
    resp = client.post(
        f"/api/v1/evaluations/{created_evaluation_id}/re-evaluate",
        json={"actor_id": "M001", "feedback": ["请重点关注代码质量"]},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == created_evaluation_id
    assert data["status"] in ("manager_review", "hr_audit")


def test_get_employee_dashboard(client, mock_app_state, created_evaluation_id):
    resp = client.get(
        "/api/v1/employees/E1001/dashboard",
        headers={"x-user-id": "E1001"},
    )
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


# ---------------- JWT 认证测试 ----------------


def test_auth_register_and_login(client, mock_app_state):
    """注册 → 登录 → /me 全流程"""
    register_payload = {
        "user_id": "E2001",
        "name": "测试员工",
        "email": "test-register@empvalue.ai",
        "password": "test123456",
        "role": "employee",
        "department": "测试部",
    }
    resp = client.post("/api/v1/auth/register", json=register_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"]
    assert data["role"] == "employee"
    assert data["user_id"] == "E2001"

    # 登录
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test-register@empvalue.ai", "password": "test123456"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token

    # /me
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()
    assert me["user_id"] == "E2001"
    assert me["email"] == "test-register@empvalue.ai"


def test_auth_login_wrong_password(client, mock_app_state):
    """错误密码应返回 401"""
    client.post(
        "/api/v1/auth/register",
        json={
            "user_id": "E2002",
            "name": "测试员工2",
            "email": "wrong-pwd@empvalue.ai",
            "password": "correct123",
            "role": "employee",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong-pwd@empvalue.ai", "password": "wrong123"},
    )
    assert resp.status_code == 401


def test_auth_register_duplicate_email(client, mock_app_state):
    """重复邮箱应返回 409"""
    payload = {
        "user_id": "E2003",
        "name": "测试员工3",
        "email": "dup@empvalue.ai",
        "password": "test123456",
        "role": "employee",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    payload["user_id"] = "E2004"
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_auth_jwt_blocks_invalid_token(client, mock_app_state):
    """无效 token 应返回 401"""
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


def test_auth_jwt_role_enforced(client, mock_app_state):
    """JWT token 中的角色应被强制校验"""
    # 注册 employee
    client.post(
        "/api/v1/auth/register",
        json={
            "user_id": "E2005",
            "name": "普通员工",
            "email": "role-test@empvalue.ai",
            "password": "test123456",
            "role": "employee",
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "role-test@empvalue.ai", "password": "test123456"},
    ).json()["access_token"]

    # employee 不应能访问 admin 接口
    resp = client.get(
        "/api/v1/admin/model-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_auth_seed_demo_users(client, mock_app_state):
    """初始化演示账号"""
    resp = client.post("/api/v1/auth/seed-demo-users")
    assert resp.status_code == 200
    data = resp.json()
    assert "created" in data
    # 用演示账号登录
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@empvalue.ai", "password": "empvalue123"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "employee"


# ---------------- LangGraph 原生 interrupt 测试 ----------------


def test_interrupt_flow_approve(client, mock_app_state):
    """interrupt 工作流：启动 → 暂停 → 恢复审批通过"""
    payload = {
        "employee_id": "E3001",
        "period": "2026-W26",
        "raw_inputs": [
            {"input_id": "daily-int-001", "content": "完成了 interrupt 审批流开发"},
        ],
    }
    # 1. 启动，应触发 interrupt
    resp = client.post("/api/v1/evaluations-interrupt", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_review"
    thread_id = data["thread_id"]
    assert thread_id.startswith("thread-")
    assert data["interrupt"]["node"] == "manager_review"

    # 2. 查询状态
    resp = client.get(
        f"/api/v1/evaluations-interrupt/{thread_id}/state",
        headers={"x-user-role": "manager"},
    )
    assert resp.status_code == 200
    state = resp.json()
    assert state["thread_id"] == thread_id

    # 3. 恢复：审批通过
    resp = client.post(
        f"/api/v1/evaluations-interrupt/{thread_id}/resume",
        json={"action": "approve", "comment": "同意"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "approved"
    assert result["evaluation"]["status"] == "approved"
    assert result["evaluation"]["approver_id"] == "M001"


def test_interrupt_flow_reject(client, mock_app_state):
    """interrupt 工作流：驳回"""
    payload = {
        "employee_id": "E3002",
        "period": "2026-W26",
        "raw_inputs": [
            {"input_id": "daily-int-002", "content": "测试驳回流程"},
        ],
    }
    resp = client.post("/api/v1/evaluations-interrupt", json=payload)
    thread_id = resp.json()["thread_id"]

    resp = client.post(
        f"/api/v1/evaluations-interrupt/{thread_id}/resume",
        json={"action": "reject", "comment": "证据不足"},
        headers={"x-user-role": "manager", "x-user-id": "M001"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_interrupt_resume_unknown_thread(client, mock_app_state):
    """恢复不存在的线程应 404"""
    resp = client.post(
        "/api/v1/evaluations-interrupt/nonexistent-thread/resume",
        json={"action": "approve"},
        headers={"x-user-role": "manager"},
    )
    assert resp.status_code == 404


def test_interrupt_resume_invalid_action(client, mock_app_state):
    """恢复时 action 非法应 400"""
    payload = {
        "employee_id": "E3003",
        "period": "2026-W26",
        "raw_inputs": [{"input_id": "d1", "content": "测试非法 action"}],
    }
    resp = client.post("/api/v1/evaluations-interrupt", json=payload)
    thread_id = resp.json()["thread_id"]

    resp = client.post(
        f"/api/v1/evaluations-interrupt/{thread_id}/resume",
        json={"action": "invalid_action"},
        headers={"x-user-role": "manager"},
    )
    assert resp.status_code == 400
