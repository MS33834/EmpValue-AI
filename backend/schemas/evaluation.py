"""
EmpValue-AI 评估输出 Schema
使用 Pydantic v2 强制约束 LLM 输出，确保下游处理稳定、可审计。
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from models.constants import EvaluationStatus


class DimensionScore(BaseModel):
    """单一维度得分，强制引用原始证据与改进动作。"""

    dimension: str = Field(
        ...,
        description="评估维度，例如：执行力、协作沟通、创新能力、学习成长、业务影响",
    )
    score: float = Field(
        ...,
        ge=0,
        le=100,
        description="0-100 的维度得分",
    )
    evidence: List[str] = Field(
        ...,
        min_length=1,
        description="引用员工原始数据片段，必须能追溯到具体输入，禁止臆测",
    )
    improvement_actions: List[str] = Field(
        ...,
        min_length=1,
        description="具体、可执行、面向未来的改进建议",
    )

    @field_validator("evidence")
    @classmethod
    def evidence_must_be_specific(cls, v: List[str]) -> List[str]:
        for item in v:
            if len(item.strip()) < 10:
                raise ValueError("证据引用过短，必须包含具体上下文")
        return v


class EmployeeView(BaseModel):
    """员工可见的建设性视图：客观、正向、无主观负面措辞。"""

    summary: str = Field(
        ...,
        min_length=20,
        description="对该周期的客观总结，聚焦事实与成长",
    )
    strengths: List[str] = Field(
        ...,
        min_length=1,
        description="具体优势，每条需附带事实依据",
    )
    growth_areas: List[DimensionScore] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="成长维度，用发展性语言表述",
    )
    next_week_focus: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="下周可聚焦的 1-5 项具体行动",
    )


class RiskFlag(BaseModel):
    """管理视图中的风险标记，用于主管快速识别问题。"""

    level: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="风险等级",
    )
    category: str = Field(
        ...,
        description="风险类别，例如：产出波动、协作摩擦、技能瓶颈、态度风险",
    )
    description: str = Field(
        ...,
        description="基于事实的风险描述",
    )
    suggested_action: str = Field(
        ...,
        description="建议采取的管理动作",
    )


class ManagerView(BaseModel):
    """管理/HR 可见的尖锐诊断视图：直接、战略、不含糖衣。"""

    harsh_assessment: str = Field(
        ...,
        min_length=30,
        description="尖锐但基于事实的总体判断，不回避问题",
    )
    risk_flags: List[RiskFlag] = Field(
        ...,
        description="识别的风险标记，无风险时返回空列表",
    )
    roi_analysis: str = Field(
        ...,
        description="从投入产出比角度对该员工的判断",
    )
    reallocation_suggestion: str = Field(
        ...,
        description="岗位/任务/团队调配建议",
    )
    hidden_issues: List[str] = Field(
        ...,
        description="员工不可见的深层判断，仅限管理/HR查看，必须有证据支撑",
    )


class AuditInfo(BaseModel):
    """审计信息，保证可解释性与可追溯性。"""

    model_name: str = Field(..., description="实际使用的模型名称")
    model_tier: Literal["L0", "L1", "L2", "L3"] = Field(
        ..., description="模型档位"
    )
    confidence_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="AI 对本次评估的综合置信度",
    )
    raw_data_refs: List[str] = Field(
        ..., description="评估引用的原始数据 ID/摘要列表"
    )
    triggered_rules: List[str] = Field(
        ..., description="本次评估触发的规则或策略说明"
    )
    processing_time_ms: int = Field(..., ge=0, description="处理耗时（毫秒）")
    prompt_version: str = Field(..., description="使用的 Prompt 版本号")


class EmployeeEvaluation(BaseModel):
    """一次完整的员工评估结果。"""

    evaluation_id: str = Field(..., description="评估唯一 ID")
    employee_id: str = Field(..., description="员工唯一 ID")
    period: str = Field(..., description="评估周期，例如：2026-W25")
    overall_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="综合得分",
    )
    employee_view: EmployeeView
    manager_view: ManagerView
    audit: AuditInfo
    status: Literal[
        EvaluationStatus.AI_DRAFTED,
        EvaluationStatus.MANAGER_REVIEW,
        EvaluationStatus.HR_AUDIT,
        EvaluationStatus.APPROVED,
        EvaluationStatus.REJECTED,
    ] = Field(..., description="审批状态")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = Field(None, description="审批通过时间")
    approver_id: Optional[str] = Field(None, description="审批人 ID")

    @field_validator("overall_score")
    @classmethod
    def score_rounded(cls, v: float) -> float:
        return round(v, 2)
