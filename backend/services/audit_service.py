"""
审计日志服务
记录所有对评估结果的关键操作，便于 HR 复核与合规追溯。
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AuditLog(BaseModel):
    """审计日志条目"""

    log_id: str
    evaluation_id: Optional[str] = None
    employee_id: Optional[str] = None
    actor_id: str
    action: str
    details: Optional[Dict] = None
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditService:
    """审计服务（内存实现，生产环境应持久化到数据库）"""

    def __init__(self):
        self._logs: List[AuditLog] = []
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"LOG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._counter:06d}"

    def log(
        self,
        actor_id: str,
        action: str,
        evaluation_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            log_id=self._next_id(),
            actor_id=actor_id,
            action=action,
            evaluation_id=evaluation_id,
            employee_id=employee_id,
            details=details,
            ip_address=ip_address,
        )
        self._logs.append(entry)
        return entry

    def get_logs(
        self,
        evaluation_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        logs = self._logs
        if evaluation_id:
            logs = [l for l in logs if l.evaluation_id == evaluation_id]
        if employee_id:
            logs = [l for l in logs if l.employee_id == employee_id]
        return logs[-limit:]
