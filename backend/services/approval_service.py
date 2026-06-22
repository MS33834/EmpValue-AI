"""
审批流服务
管理评估状态机的合法转换与审批记录，持久化到数据库。
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ApprovalAction


class ApprovalService:
    """审批服务（数据库实现）"""

    VALID_TRANSITIONS = {
        "ai_drafted": {"approve": "approved", "reject": "rejected", "request_hr_review": "hr_audit"},
        "manager_review": {"approve": "approved", "reject": "rejected", "request_hr_review": "hr_audit"},
        "hr_audit": {"approve": "approved", "reject": "rejected", "request_manager_review": "manager_review"},
        "approved": {},
        "rejected": {"appeal": "manager_review"},
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def can_transition(current_status: str, action: str) -> bool:
        return action in ApprovalService.VALID_TRANSITIONS.get(current_status, {})

    async def transition(
        self,
        evaluation_id: str,
        current_status: str,
        action: Literal["approve", "reject", "request_hr_review", "request_manager_review", "appeal"],
        actor_id: str,
        actor_role: str,
        comment: Optional[str] = None,
    ) -> str:
        """执行状态转换，写入数据库，返回新状态"""
        if not self.can_transition(current_status, action):
            raise ValueError(f"非法状态转换: {current_status} -> {action}")

        new_status = self.VALID_TRANSITIONS[current_status][action]
        action_record = ApprovalAction(
            action_id=f"ACT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{actor_id}",
            evaluation_id=evaluation_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            comment=comment,
        )
        self.session.add(action_record)
        await self.session.commit()
        return new_status

    async def get_history(self, evaluation_id: str) -> List[ApprovalAction]:
        result = await self.session.execute(
            select(ApprovalAction)
            .where(ApprovalAction.evaluation_id == evaluation_id)
            .order_by(ApprovalAction.created_at.asc())
        )
        return result.scalars().all()

    @staticmethod
    def get_allowed_actions(current_status: str) -> List[str]:
        return list(ApprovalService.VALID_TRANSITIONS.get(current_status, {}).keys())
