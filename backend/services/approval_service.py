"""
审批流服务
管理评估状态机的合法转换与审批记录，持久化到数据库。
注意：transition 不在内部 commit，由调用方控制事务边界以保证原子性。
"""

import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ApprovalAction, Evaluation
from models.constants import EvaluationStatus


class ApprovalService:
    """审批服务（数据库实现）"""

    VALID_TRANSITIONS = {
        EvaluationStatus.AI_DRAFTED: {
            "approve": EvaluationStatus.APPROVED,
            "reject": EvaluationStatus.REJECTED,
            "request_hr_review": EvaluationStatus.HR_AUDIT,
        },
        EvaluationStatus.MANAGER_REVIEW: {
            "approve": EvaluationStatus.APPROVED,
            "reject": EvaluationStatus.REJECTED,
            "request_hr_review": EvaluationStatus.HR_AUDIT,
        },
        EvaluationStatus.HR_AUDIT: {
            "approve": EvaluationStatus.APPROVED,
            "reject": EvaluationStatus.REJECTED,
            "request_manager_review": EvaluationStatus.MANAGER_REVIEW,
        },
        EvaluationStatus.APPROVED: {"appeal": EvaluationStatus.MANAGER_REVIEW},
        EvaluationStatus.REJECTED: {"appeal": EvaluationStatus.MANAGER_REVIEW},
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def can_transition(current_status: str, action: str) -> bool:
        return action in ApprovalService.VALID_TRANSITIONS.get(current_status, {})

    async def transition_status(
        self,
        evaluation_id: str,
        action: Literal["approve", "reject", "request_hr_review", "request_manager_review", "appeal"],
        actor_id: str,
        actor_role: str,
        comment: Optional[str] = None,
        approver_id: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        原子执行状态转换：使用 FOR UPDATE 查询 evaluation，校验当前状态合法性，
        更新 evaluation 状态，并写入审批记录。返回 (old_status, new_status)。
        不 commit，由调用方控制事务边界。
        """
        result = await self.session.execute(
            select(Evaluation)
            .where(Evaluation.evaluation_id == evaluation_id)
            .with_for_update()
        )
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            raise ValueError(f"评估不存在: {evaluation_id}")

        current_status = evaluation.status
        if not self.can_transition(current_status, action):
            raise ValueError(f"非法状态转换: {current_status} -> {action}")

        new_status = self.VALID_TRANSITIONS[current_status][action]
        evaluation.status = new_status

        if new_status == EvaluationStatus.APPROVED:
            evaluation.approved_at = datetime.now(timezone.utc)
            if approver_id:
                evaluation.approver_id = approver_id
        elif current_status == EvaluationStatus.APPROVED and new_status != EvaluationStatus.APPROVED:
            evaluation.approved_at = None
            evaluation.approver_id = None
        elif approver_id:
            evaluation.approver_id = approver_id

        action_record = ApprovalAction(
            action_id=f"ACT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{actor_id}-{uuid.uuid4().hex[:6]}",
            evaluation_id=evaluation_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            comment=comment,
        )
        self.session.add(action_record)
        return current_status, new_status

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

