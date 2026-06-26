"""
services/audit_service.py 单元测试
使用独立临时 SQLite 异步数据库，覆盖 log / get_logs / list_logs。
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.database import Base
from models import AuditLog  # 触发模型注册
from services.audit_service import AuditService


@pytest.fixture
async def db_session():
    """每个测试使用独立临时 SQLite 异步数据库"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_url = f"sqlite+aiosqlite:///{tmp.name}"
    engine = create_async_engine(db_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
    )
    async with SessionLocal() as session:
        yield session
    await engine.dispose()
    Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def audit_service(db_session):
    return AuditService(db_session)


# ---------------- log ----------------


async def test_log_creates_entry_with_complete_fields(audit_service, db_session):
    """log 应写入完整字段并返回 AuditLog 对象"""
    entry = await audit_service.log(
        actor_id="M001",
        action="approve",
        evaluation_id="EVAL-001",
        employee_id="E1001",
        details={"comment": "同意", "score": 88},
        ip_address="10.0.0.1",
    )
    await db_session.flush()

    assert entry.log_id.startswith("LOG-")
    assert entry.actor_id == "M001"
    assert entry.action == "approve"
    assert entry.evaluation_id == "EVAL-001"
    assert entry.employee_id == "E1001"
    assert entry.details == {"comment": "同意", "score": 88}
    assert entry.ip_address == "10.0.0.1"
    assert entry.created_at is not None


async def test_log_with_minimal_fields(audit_service, db_session):
    """仅必填字段时，可选字段应为合理默认"""
    entry = await audit_service.log(actor_id="U001", action="view")
    await db_session.flush()

    assert entry.evaluation_id is None
    assert entry.employee_id is None
    assert entry.details == {}  # details or {} 默认空 dict
    assert entry.ip_address is None


async def test_log_details_none_defaults_to_empty_dict(audit_service, db_session):
    """details 显式传 None 时应存储为空 dict"""
    entry = await audit_service.log(actor_id="U002", action="export", details=None)
    await db_session.flush()
    assert entry.details == {}


async def test_log_log_id_is_unique(audit_service, db_session):
    """多次 log 应生成不同 log_id"""
    e1 = await audit_service.log(actor_id="A", action="x")
    e2 = await audit_service.log(actor_id="A", action="x")
    await db_session.flush()
    assert e1.log_id != e2.log_id


# ---------------- get_logs ----------------


async def test_get_logs_by_evaluation_id(audit_service, db_session):
    """get_logs 按 evaluation_id 过滤"""
    await audit_service.log(actor_id="M001", action="approve", evaluation_id="EVAL-A")
    await audit_service.log(actor_id="M002", action="reject", evaluation_id="EVAL-B")
    await audit_service.log(actor_id="M001", action="appeal", evaluation_id="EVAL-A")
    await db_session.flush()

    logs = await audit_service.get_logs(evaluation_id="EVAL-A")
    assert len(logs) == 2
    assert all(l.evaluation_id == "EVAL-A" for l in logs)


async def test_get_logs_by_employee_id(audit_service, db_session):
    """get_logs 按 employee_id 过滤"""
    await audit_service.log(actor_id="A", action="x", employee_id="E1001")
    await audit_service.log(actor_id="A", action="y", employee_id="E1002")
    await audit_service.log(actor_id="A", action="z", employee_id="E1001")
    await db_session.flush()

    logs = await audit_service.get_logs(employee_id="E1001")
    assert len(logs) == 2
    assert all(l.employee_id == "E1001" for l in logs)


async def test_get_logs_respects_limit(audit_service, db_session):
    """get_logs 应尊重 limit 参数"""
    for i in range(5):
        await audit_service.log(actor_id="A", action=f"a{i}")
    await db_session.flush()

    logs = await audit_service.get_logs(limit=2)
    assert len(logs) == 2


async def test_get_logs_returns_empty_when_no_match(audit_service, db_session):
    """无匹配记录时返回空列表"""
    await audit_service.log(actor_id="A", action="x", evaluation_id="EVAL-1")
    await db_session.flush()

    logs = await audit_service.get_logs(evaluation_id="EVAL-NOPE")
    assert logs == []


async def test_get_logs_ordered_by_created_at_desc(audit_service, db_session):
    """get_logs 应按 created_at 倒序返回"""
    import time

    e1 = await audit_service.log(actor_id="A", action="first")
    await db_session.flush()
    time.sleep(0.01)
    e2 = await audit_service.log(actor_id="A", action="second")
    await db_session.flush()

    logs = await audit_service.get_logs()
    assert logs[0].action == "second"
    assert logs[1].action == "first"


# ---------------- list_logs ----------------


async def test_list_logs_default_pagination(audit_service, db_session):
    """list_logs 默认分页返回结构与字段"""
    await audit_service.log(actor_id="A", action="approve", evaluation_id="E1", employee_id="E1001", ip_address="1.1.1.1")
    await db_session.flush()

    result = await audit_service.list_logs()
    assert result["total"] == 1
    assert result["page"] == 1
    assert result["page_size"] == 20
    assert len(result["logs"]) == 1
    log = result["logs"][0]
    assert log["actor_id"] == "A"
    assert log["action"] == "approve"
    assert log["evaluation_id"] == "E1"
    assert log["employee_id"] == "E1001"
    assert log["ip_address"] == "1.1.1.1"
    assert "created_at" in log and isinstance(log["created_at"], str)


async def test_list_logs_pagination(audit_service, db_session):
    """list_logs 分页：page_size 控制每页条数，total 为总数"""
    for i in range(7):
        await audit_service.log(actor_id="A", action=f"a{i}")
    await db_session.flush()

    page1 = await audit_service.list_logs(page=1, page_size=3)
    page2 = await audit_service.list_logs(page=2, page_size=3)
    page3 = await audit_service.list_logs(page=3, page_size=3)

    assert page1["total"] == 7
    assert len(page1["logs"]) == 3
    assert len(page2["logs"]) == 3
    assert len(page3["logs"]) == 1


async def test_list_logs_filter_by_actor_id(audit_service, db_session):
    """list_logs 按 actor_id 筛选"""
    await audit_service.log(actor_id="M001", action="approve")
    await audit_service.log(actor_id="M002", action="approve")
    await audit_service.log(actor_id="M001", action="reject")
    await db_session.flush()

    result = await audit_service.list_logs(actor_id="M001")
    assert result["total"] == 2
    assert all(l["actor_id"] == "M001" for l in result["logs"])


async def test_list_logs_filter_by_action(audit_service, db_session):
    """list_logs 按 action 筛选"""
    await audit_service.log(actor_id="A", action="approve")
    await audit_service.log(actor_id="B", action="reject")
    await audit_service.log(actor_id="C", action="approve")
    await db_session.flush()

    result = await audit_service.list_logs(action="approve")
    assert result["total"] == 2
    assert all(l["action"] == "approve" for l in result["logs"])


async def test_list_logs_combined_filter(audit_service, db_session):
    """list_logs 同时按 actor_id 与 action 筛选"""
    await audit_service.log(actor_id="M001", action="approve")
    await audit_service.log(actor_id="M001", action="reject")
    await audit_service.log(actor_id="M002", action="approve")
    await db_session.flush()

    result = await audit_service.list_logs(actor_id="M001", action="approve")
    assert result["total"] == 1
    assert result["logs"][0]["actor_id"] == "M001"
    assert result["logs"][0]["action"] == "approve"


async def test_list_logs_empty_when_no_match(audit_service, db_session):
    """无匹配记录时 total=0 且 logs 为空"""
    await audit_service.log(actor_id="A", action="x")
    await db_session.flush()

    result = await audit_service.list_logs(actor_id="NOBODY")
    assert result["total"] == 0
    assert result["logs"] == []


async def test_list_logs_page_beyond_range_returns_empty(audit_service, db_session):
    """页码超出范围时返回空 logs 但 total 仍正确"""
    for i in range(3):
        await audit_service.log(actor_id="A", action=f"a{i}")
    await db_session.flush()

    result = await audit_service.list_logs(page=10, page_size=20)
    assert result["total"] == 3
    assert result["page"] == 10
    assert result["logs"] == []
