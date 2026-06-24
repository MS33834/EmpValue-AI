"""
审计日志服务
记录所有对评估结果的关键操作，便于 HR 复核与合规追溯。
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog


class AuditService:
    """审计服务（数据库实现）"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        actor_id: str,
        action: str,
        evaluation_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """记录审计日志（不 commit，由调用方控制事务）"""
        entry = AuditLog(
            log_id=f"LOG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            actor_id=actor_id,
            action=action,
            evaluation_id=evaluation_id,
            employee_id=employee_id,
            details=details or {},
            ip_address=ip_address,
        )
        self.session.add(entry)
        return entry

    async def get_logs(
        self,
        evaluation_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if evaluation_id:
            stmt = stmt.where(AuditLog.evaluation_id == evaluation_id)
        if employee_id:
            stmt = stmt.where(AuditLog.employee_id == employee_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
