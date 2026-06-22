"""
评估相关数据库服务
封装 evaluations、raw_inputs、feedback、users、memories、company_kb 的 CRUD。
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CompanyKB, Evaluation, Feedback, Memory, RawInput, User


class EvaluationService:
    """评估服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_raw_input(self, data: Dict) -> RawInput:
        """创建原始输入"""
        raw = RawInput(
            input_id=data.get("input_id"),
            employee_id=data["employee_id"],
            period=data["period"],
            type=data.get("type", "daily_report"),
            content=data["content"],
            attachments=data.get("attachments", []),
        )
        self.session.add(raw)
        await self.session.commit()
        await self.session.refresh(raw)
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
        """保存评估结果"""
        evaluation = Evaluation(
            evaluation_id=evaluation_data["evaluation_id"],
            employee_id=evaluation_data["employee_id"],
            period=evaluation_data["period"],
            overall_score=evaluation_data["overall_score"],
            employee_view=evaluation_data["employee_view"],
            manager_view=evaluation_data["manager_view"],
            audit=evaluation_data["audit"],
            status=evaluation_data.get("status", "ai_drafted"),
        )
        self.session.add(evaluation)
        await self.session.commit()
        await self.session.refresh(evaluation)
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
        evaluation = await self.get_evaluation(evaluation_id)
        if not evaluation:
            return None
        evaluation.status = new_status
        if approver_id:
            evaluation.approver_id = approver_id
        if new_status == "approved":
            evaluation.approved_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(evaluation)
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
        feedback = Feedback(
            feedback_id=data.get("feedback_id"),
            evaluation_id=data["evaluation_id"],
            employee_id=data["employee_id"],
            type=data.get("type", "feedback"),
            content=data["content"],
        )
        self.session.add(feedback)
        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback

    async def get_user(self, user_id: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(self, data: Dict) -> User:
        user = User(
            user_id=data["user_id"],
            name=data["name"],
            email=data.get("email"),
            role=data.get("role", "employee"),
            department=data.get("department"),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
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
        """添加员工记忆"""
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
        await self.session.commit()
        await self.session.refresh(mem)
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
        doc = CompanyKB(
            kb_id=data["kb_id"],
            title=data["title"],
            content=data["content"],
            metadata_=data.get("metadata", {}),
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
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
