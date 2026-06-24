"""
审计日志服务
记录所有对评估结果的关键操作，便于 HR 复核与合规追溯。
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
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

    async def list_logs(
        self,
        actor_id: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict:
        """分页查询审计日志，支持按操作人、动作筛选"""
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_stmt = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_stmt)
        logs = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "logs": [
                {
                    "log_id": log.log_id,
                    "actor_id": log.actor_id,
                    "action": log.action,
                    "evaluation_id": log.evaluation_id,
                    "employee_id": log.employee_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ],
        }
