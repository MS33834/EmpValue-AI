"""
评估相关数据库服务
封装 evaluations、raw_inputs、feedback、users、memories、company_kb 的 CRUD。
事务边界统一由路由层控制：service 层方法不 commit，仅 add/update 后返回。
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CompanyKB, DimensionScore, Evaluation, EvidenceRef, Feedback, Memory, RawInput, User
from models.constants import EvaluationStatus


class EvaluationService:
    """评估服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_raw_input(self, data: Dict) -> RawInput:
        """创建原始输入（不 commit，由调用方控制事务）"""
        raw = RawInput(
            input_id=data.get("input_id") or f"INPUT-{uuid.uuid4().hex[:12]}",
            employee_id=data["employee_id"],
            period=data["period"],
            type=data.get("type", "daily_report"),
            content=data["content"],
            attachments=data.get("attachments", []),
        )
        self.session.add(raw)
        await self.session.flush()
        return raw

    async def get_raw_input(self, input_id: str) -> Optional[RawInput]:
        result = await self.session.execute(
            select(RawInput).where(RawInput.input_id == input_id)
        )
        return result.scalar_one_or_none()

    async def list_raw_inputs(
        self,
        employee_id: Optional[str] = None,
        period: Optional[str] = None,
        limit: int = 100,
    ) -> List[RawInput]:
        stmt = select(RawInput).order_by(RawInput.created_at.desc()).limit(limit)
        if employee_id:
            stmt = stmt.where(RawInput.employee_id == employee_id)
        if period:
            stmt = stmt.where(RawInput.period == period)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_evaluation(self, evaluation_data: Dict) -> Evaluation:
        """保存评估结果，并同步拆分维度得分与证据引用（不 commit，由调用方控制事务）"""
        evaluation = Evaluation(
            evaluation_id=evaluation_data["evaluation_id"],
            employee_id=evaluation_data["employee_id"],
            period=evaluation_data["period"],
            overall_score=evaluation_data["overall_score"],
            employee_view=evaluation_data["employee_view"],
            manager_view=evaluation_data["manager_view"],
            audit=evaluation_data["audit"],
            status=evaluation_data.get("status", EvaluationStatus.AI_DRAFTED),
        )
        self.session.add(evaluation)

        # 同步拆分维度得分与证据引用，便于横向分析
        growth_areas = evaluation_data.get("employee_view", {}).get("growth_areas", [])
        for area in growth_areas:
            dim = DimensionScore(
                evaluation_id=evaluation.evaluation_id,
                employee_id=evaluation_data["employee_id"],
                period=evaluation_data["period"],
                dimension=area.get("dimension", ""),
                score=area.get("score", 0),
                improvement_actions=area.get("improvement_actions", []),
            )
            self.session.add(dim)
            for evidence in area.get("evidence", []):
                ref = EvidenceRef(
                    evaluation_id=evaluation.evaluation_id,
                    dimension=area.get("dimension", ""),
                    evidence_text=evidence,
                )
                self.session.add(ref)

        await self.session.flush()
        return evaluation

    async def get_evaluation(self, evaluation_id: str) -> Optional[Evaluation]:
        result = await self.session.execute(
            select(Evaluation).where(Evaluation.evaluation_id == evaluation_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        evaluation_id: str,
        new_status: str,
        approver_id: Optional[str] = None,
    ) -> Optional[Evaluation]:
        """更新评估状态（不 commit，由调用方控制事务）"""
        evaluation = await self.get_evaluation(evaluation_id)
        if not evaluation:
            return None
        old_status = evaluation.status
        evaluation.status = new_status

        if new_status == EvaluationStatus.APPROVED:
            evaluation.approved_at = datetime.now(timezone.utc)
            if approver_id:
                evaluation.approver_id = approver_id
        elif old_status == EvaluationStatus.APPROVED and new_status != EvaluationStatus.APPROVED:
            # 离开 approved 状态时重置审批信息
            evaluation.approved_at = None
            evaluation.approver_id = None
        elif approver_id:
            evaluation.approver_id = approver_id

        return evaluation

    async def update_evaluation(
        self,
        evaluation_id: str,
        evaluation_data: Dict,
    ) -> Optional[Evaluation]:
        """完整更新评估内容（不 commit，由调用方控制事务）"""
        evaluation = await self.get_evaluation(evaluation_id)
        if not evaluation:
            return None
        old_status = evaluation.status
        evaluation.employee_view = evaluation_data.get("employee_view", evaluation.employee_view)
        evaluation.manager_view = evaluation_data.get("manager_view", evaluation.manager_view)
        evaluation.audit = evaluation_data.get("audit", evaluation.audit)
        evaluation.overall_score = evaluation_data.get("overall_score", evaluation.overall_score)
        evaluation.status = evaluation_data.get("status", evaluation.status)

        new_status = evaluation.status
        if new_status == EvaluationStatus.APPROVED:
            evaluation.approved_at = datetime.now(timezone.utc)
        elif old_status == EvaluationStatus.APPROVED and new_status != EvaluationStatus.APPROVED:
            evaluation.approved_at = None
            evaluation.approver_id = None

        return evaluation

    async def list_evaluations(
        self,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Evaluation]:
        stmt = select(Evaluation).order_by(Evaluation.created_at.desc()).limit(limit).offset(offset)
        if employee_id:
            stmt = stmt.where(Evaluation.employee_id == employee_id)
        if status:
            stmt = stmt.where(Evaluation.status == status)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_feedback(self, data: Dict) -> Feedback:
        """创建反馈（不 commit，由调用方控制事务）"""
        feedback = Feedback(
            feedback_id=data.get("feedback_id") or f"FB-{uuid.uuid4().hex[:12]}",
            evaluation_id=data["evaluation_id"],
            employee_id=data["employee_id"],
            type=data.get("type", "feedback"),
            content=data["content"],
        )
        self.session.add(feedback)
        await self.session.flush()
        return feedback

    async def get_user(self, user_id: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create_user(self, data: Dict) -> User:
        """创建用户（不 commit，由调用方控制事务）"""
        user = User(
            user_id=data["user_id"],
            name=data["name"],
            email=data.get("email"),
            role=data.get("role", "employee"),
            department=data.get("department"),
            password_hash=data.get("password_hash"),
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def ensure_user_exists(self, user_id: str, name: str = "", role: str = "employee") -> User:
        user = await self.get_user(user_id)
        if user:
            return user
        return await self.create_user({"user_id": user_id, "name": name or user_id, "role": role})

    async def get_employee_history(
        self,
        employee_id: str,
        period: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """从 memories 表获取员工历史记忆摘要"""
        stmt = (
            select(Memory)
            .where(Memory.employee_id == employee_id)
            .order_by(Memory.period.desc())
            .limit(limit)
        )
        if period:
            stmt = stmt.where(Memory.period != period)
        result = await self.session.execute(stmt)
        return [m.payload for m in result.scalars().all()]

    async def add_memory(self, employee_id: str, memory: Dict) -> Memory:
        """添加员工记忆（不 commit，由调用方控制事务）"""
        existing = await self.session.execute(
            select(Memory).where(
                Memory.employee_id == employee_id,
                Memory.period == memory.get("period", ""),
            )
        )
        mem = existing.scalar_one_or_none()
        if mem:
            mem.content = memory.get("summary", "")
            mem.payload = memory
        else:
            mem = Memory(
                employee_id=employee_id,
                period=memory.get("period", ""),
                content=memory.get("summary", ""),
                payload=memory,
            )
            self.session.add(mem)
        await self.session.flush()
        return mem

    async def query_company_kb(self, query: str, top_k: int = 5) -> List[Dict]:
        """简单关键词检索公司知识库（后续可替换为向量检索）"""
        result = await self.session.execute(select(CompanyKB))
        docs = result.scalars().all()
        query_words = set(query.lower().split())
        scored = []
        for doc in docs:
            text = f"{doc.title} {doc.content}".lower()
            score = len(query_words & set(text.split()))
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"kb_id": d.kb_id, "title": d.title, "content": d.content, "metadata": d.metadata_}
            for _, d in scored[:top_k]
        ]

    async def create_kb_doc(self, data: Dict) -> CompanyKB:
        """创建知识库文档（不 commit，由调用方控制事务）"""
        doc = CompanyKB(
            kb_id=data["kb_id"],
            title=data["title"],
            content=data["content"],
            metadata_=data.get("metadata", {}),
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_team_analytics(self, team_members: List[str]) -> Dict:
        """团队分析聚合"""
        stmt = (
            select(
                Evaluation.employee_id,
                func.avg(Evaluation.overall_score).label("avg_score"),
                func.count(Evaluation.id).label("eval_count"),
            )
            .where(Evaluation.employee_id.in_(team_members))
            .group_by(Evaluation.employee_id)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return {
            "members": [
                {
                    "employee_id": row.employee_id,
                    "avg_score": round(row.avg_score or 0, 2),
                    "eval_count": row.eval_count,
                }
                for row in rows
            ],
            "overall_avg": round(
                sum(r.avg_score or 0 for r in rows) / len(rows), 2
            ) if rows else 0,
        }
