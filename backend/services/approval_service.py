"""
审批流服务
管理评估状态机的合法转换与审批记录。
"""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ApprovalAction(BaseModel):
    """审批动作记录"""

    action_id: str
    evaluation_id: str
    actor_id: str
    actor_role: str
    action: Literal["approve", "reject", "request_hr_review", "appeal"]
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalService:
    """审批服务（内存实现，生产环境应持久化到数据库）"""

    VALID_TRANSITIONS = {
        "ai_drafted": {"approve": "approved", "reject": "rejected", "request_hr_review": "hr_audit"},
        "manager_review": {"approve": "approved", "reject": "rejected", "request_hr_review": "hr_audit"},
        "hr_audit": {"approve": "approved", "reject": "rejected", "request_manager_review": "manager_review"},
        "approved": {},
        "rejected": {"appeal": "manager_review"},
    }

    def __init__(self):
        self._actions: Dict[str, List[ApprovalAction]] = {}

    def can_transition(
        self,
        current_status: str,
        action: str,
    ) -> bool:
        return action in self.VALID_TRANSITIONS.get(current_status, {})

    def transition(
        self,
        evaluation_id: str,
        current_status: str,
        action: str,
        actor_id: str,
        actor_role: str,
        comment: Optional[str] = None,
    ) -> str:
        """执行状态转换，返回新状态"""
        if not self.can_transition(current_status, action):
            raise ValueError(
                f"非法状态转换: {current_status} -> {action}"
            )
        new_status = self.VALID_TRANSITIONS[current_status][action]
        action_record = ApprovalAction(
            action_id=f"ACT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{actor_id}",
            evaluation_id=evaluation_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,  # type: ignore
            comment=comment,
        )
        self._actions.setdefault(evaluation_id, []).append(action_record)
        return new_status

    def get_history(self, evaluation_id: str) -> List[ApprovalAction]:
        return self._actions.get(evaluation_id, [])

    def get_allowed_actions(self, current_status: str) -> List[str]:
        return list(self.VALID_TRANSITIONS.get(current_status, {}).keys())
