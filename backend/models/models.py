"""
SQLAlchemy 数据模型定义
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """系统用户（员工/主管/HR/管理员）"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="employee")
    department: Mapped[str] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RawInput(Base):
    """员工原始输入：日报、任务进度、截图、语音等"""

    __tablename__ = "raw_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    input_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    employee_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False, default="daily_report")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        UniqueConstraint("employee_id", "period", "input_id", name="uix_raw_input"),
    )


class Evaluation(Base):
    """员工评估结果主表"""

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evaluation_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    employee_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    employee_view: Mapped[dict] = mapped_column(JSON, nullable=False)
    manager_view: Mapped[dict] = mapped_column(JSON, nullable=False)
    audit: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ai_drafted",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    approver_id: Mapped[str] = mapped_column(String(64), nullable=True)


class ApprovalAction(Base):
    """审批流动作记录"""

    __tablename__ = "approval_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditLog(Base):
    """审计日志"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    log_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(128), index=True, nullable=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Feedback(Base):
    """员工反馈与申诉"""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feedback_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    employee_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="feedback")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Memory(Base):
    """员工长期记忆（可后续对接向量库，当前用关系表兜底）"""

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        UniqueConstraint("employee_id", "period", name="uix_employee_period_memory"),
    )


class CompanyKB(Base):
    """公司知识库（评分标准、价值观、培训材料）"""

    __tablename__ = "company_kb"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    kb_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
