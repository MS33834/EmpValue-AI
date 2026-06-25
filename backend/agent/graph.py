"""
LangGraph 评估工作流
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, Literal, Optional

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from core.guards import InputGuard, OutputGuard
from core.model_router import ModelRouter
from core.multimodal import MultimodalCleaner
from core.providers.base import ChatMessage
from models.constants import EvaluationStatus
from schemas import EmployeeEvaluation

from .prompt_loader import PromptLoader
from .state import EvaluationState
from .tools import AgentToolkit

logger = logging.getLogger(__name__)


def create_evaluation_graph(
    toolkit: AgentToolkit,
    model_router: ModelRouter,
    prompt_loader: PromptLoader,
    prompt_name: str = "daily_evaluation",
    input_guard: Optional[InputGuard] = None,
    output_guard: Optional[OutputGuard] = None,
    multimodal_cleaner: Optional[MultimodalCleaner] = None,
):
    """创建评估工作流图"""

    input_guard = input_guard or InputGuard()
    output_guard = output_guard or OutputGuard()
    multimodal_cleaner = multimodal_cleaner or MultimodalCleaner()

    async def input_sanitizer(state: EvaluationState) -> EvaluationState:
        """输入护栏：检查 Prompt 注入与恶意内容"""
        result = input_guard.check(state["raw_inputs"])
        if not result.allowed:
            return {
                **state,
                "error": f"输入被拦截: {result.reason}",
                "status": "error",
                "audit_info": {"triggered_rules": result.triggered_rules},
            }
        return {
            **state,
            "status": "data_cleaning",
        }

    async def data_cleaning(state: EvaluationState) -> EvaluationState:
        """
        多模态数据清洗：对附件（图片/音频/表格/PDF/文本）抽取文本，
        合并到输入 content 中，形成 cleaned_inputs。
        """
        if state.get("error"):
            return state
        try:
            cleaned = await multimodal_cleaner.clean_inputs(state["raw_inputs"])
        except Exception as e:
            logger.warning("多模态清洗失败，降级使用原始输入: %s", e)
            cleaned = state["raw_inputs"]
        return {
            **state,
            "cleaned_inputs": cleaned,
            "status": "context_retrieval",
        }

    async def retrieve_context(state: EvaluationState) -> EvaluationState:
        """获取员工历史记忆与公司知识库"""
        if state.get("error"):
            return state
        history = await toolkit.get_employee_history(
            state["employee_id"],
            period=state["period"],
            limit=5,
        )
        kb = await toolkit.query_company_kb(
            query=f"员工评估标准 {state['employee_id']} {state['period']}",
            top_k=3,
        )
        return {
            **state,
            "employee_history": history,
            "company_kb": kb,
        }

    async def build_prompt(state: EvaluationState) -> EvaluationState:
        """渲染 System Prompt"""
        if state.get("error"):
            return state
        inputs = state.get("cleaned_inputs") or state["raw_inputs"]
        prompt = prompt_loader.render(
            name=prompt_name,
            raw_inputs=inputs,
            employee_history=state.get("employee_history") or [],
            company_kb=state.get("company_kb") or [],
            employee_id=state["employee_id"],
            period=state["period"],
        )
        return {**state, "prompt": prompt}

    async def call_llm(state: EvaluationState) -> EvaluationState:
        """调用 LLM 生成评估"""
        if state.get("error"):
            return state
        start = time.time()
        try:
            provider, tier = await model_router.get_provider_with_fallback()
            messages = [
                ChatMessage(role="system", content=state["prompt"]),
                ChatMessage(role="user", content="请根据以上输入生成评估 JSON。"),
            ]
            completion = await provider.chat_completion(
                messages=messages,
                response_format={"type": "json_object"},
            )
            processing_time_ms = int((time.time() - start) * 1000)

            audit_info = {
                "model_name": completion.model,
                "model_tier": tier,
                "confidence_score": 0.0,  # 由 parse 节点根据内容更新
                "raw_data_refs": [inp.get("input_id") for inp in state["raw_inputs"]],
                "triggered_rules": ["evidence_first", "dual_view_separation"],
                "processing_time_ms": processing_time_ms,
                "prompt_version": prompt_loader.version(prompt_name),
            }

            return {
                **state,
                "llm_raw_output": completion.content,
                "audit_info": audit_info,
                "status": EvaluationStatus.AI_DRAFTED,
            }
        except Exception as e:
            return {**state, "error": f"LLM 调用失败: {e}", "status": "error"}

    async def parse_output(state: EvaluationState) -> EvaluationState:
        """解析并校验 LLM 输出"""
        if state.get("error"):
            return state

        raw = state.get("llm_raw_output", "")
        try:
            data = json.loads(raw)
            # 补充/覆盖必要字段（防止 LLM 漏填或 Mock 数据不完整）
            data["evaluation_id"] = f"EV-{state['period']}-{state['employee_id']}-{uuid.uuid4().hex[:8]}"
            data["employee_id"] = state["employee_id"]
            data["period"] = state["period"]
            data.setdefault("status", EvaluationStatus.AI_DRAFTED)

            # 合并审计信息
            audit = data.get("audit", {})
            if state.get("audit_info"):
                audit.update(state["audit_info"])
                # 根据 evidence 数量估算置信度
                evidence_count = sum(
                    len(area.get("evidence", []))
                    for area in data.get("employee_view", {}).get("growth_areas", [])
                )
                audit["confidence_score"] = min(0.95, 0.5 + evidence_count * 0.1)
            data["audit"] = audit

            # 输出护栏：脱敏与敏感词检查
            emp_view = data.get("employee_view", {})
            mgr_view = data.get("manager_view", {})
            emp_result = output_guard.sanitize_employee_view(emp_view)
            mgr_result = output_guard.sanitize_manager_view(mgr_view)

            # 记录护栏违规（不阻断流程，但写入审计信息供追溯）
            guard_violations = emp_result.violations + mgr_result.violations
            if guard_violations:
                logger.warning("输出护栏检测到违规: %s", guard_violations)
                audit["output_guard_violations"] = guard_violations
            redacted = emp_result.redacted_entities + mgr_result.redacted_entities
            if redacted:
                audit["redacted_entities"] = redacted

            evaluation = EmployeeEvaluation.model_validate(data)
            return {
                **state,
                "parsed_evaluation": evaluation.model_dump(mode="json"),
                "status": EvaluationStatus.AI_DRAFTED,
            }
        except (json.JSONDecodeError, ValidationError) as e:
            return {**state, "error": f"输出解析失败: {e}", "status": "error"}

    async def manager_review_gate(state: EvaluationState) -> Literal["hr_audit", "manager_review", "error"]:
        """
        评估生成完成后的自动路由：
        - 高风险或低分自动进入 HR 复核
        - 其余进入主管待审批
        实际审批动作由 API 层驱动状态机完成

        注意：此路由仅设置 state["status"] 作为路由标记，
        不修改 parsed_evaluation["status"]，评估统一以 ai_drafted 入库，
        由 API 层根据路由标记驱动状态机转换。
        """
        if state.get("error"):
            return "error"
        parsed = state.get("parsed_evaluation")
        if parsed:
            score = parsed.get("overall_score", 100)
            risk_flags = parsed.get("manager_view", {}).get("risk_flags", [])
            has_critical = any(r.get("level") == "critical" for r in risk_flags)
            if score < 60 or has_critical:
                return "hr_audit"
        return "manager_review"

    async def manager_review(state: EvaluationState) -> EvaluationState:
        """主管审批路由标记：评估等待主管审批。不修改 parsed_evaluation.status，保持 ai_drafted 入库。"""
        return {**state, "status": EvaluationStatus.MANAGER_REVIEW}

    async def hr_audit(state: EvaluationState) -> EvaluationState:
        """HR 复核路由标记：高风险评估等待 HR 复核。不修改 parsed_evaluation.status，保持 ai_drafted 入库。"""
        return {**state, "status": EvaluationStatus.HR_AUDIT}

    async def finalize(state: EvaluationState) -> EvaluationState:
        """最终状态节点：保留上游设置的状态"""
        return state

    # 构建图
    builder = StateGraph(EvaluationState)
    builder.add_node("input_sanitizer", input_sanitizer)
    builder.add_node("data_cleaning", data_cleaning)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("build_prompt", build_prompt)
    builder.add_node("call_llm", call_llm)
    builder.add_node("parse_output", parse_output)
    builder.add_node("manager_review", manager_review)
    builder.add_node("hr_audit", hr_audit)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "input_sanitizer")
    builder.add_edge("input_sanitizer", "data_cleaning")
    builder.add_edge("data_cleaning", "retrieve_context")
    builder.add_edge("retrieve_context", "build_prompt")
    builder.add_edge("build_prompt", "call_llm")
    builder.add_edge("call_llm", "parse_output")
    builder.add_conditional_edges(
        "parse_output",
        manager_review_gate,
        {
            "hr_audit": "hr_audit",
            "manager_review": "manager_review",
            "error": END,
        },
    )
    builder.add_edge("manager_review", "finalize")
    builder.add_edge("hr_audit", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


def create_evaluation_graph_with_interrupt(
    toolkit: AgentToolkit,
    model_router: ModelRouter,
    prompt_loader: PromptLoader,
    prompt_name: str = "daily_evaluation",
    input_guard: Optional[InputGuard] = None,
    output_guard: Optional[OutputGuard] = None,
    multimodal_cleaner: Optional[MultimodalCleaner] = None,
    checkpointer=None,
):
    """
    创建带 LangGraph 原生 interrupt 中断点的评估工作流图。
    与 create_evaluation_graph 的区别：
    - manager_review / hr_audit 节点使用 interrupt() 暂停执行，等待人工审批
    - 必须配合 checkpointer 使用（如 MemorySaver）
    - 通过 Command(resume=...) 恢复执行
    审批恢复值格式：{"action": "approve"|"reject"|"request_hr_review", "comment": "...", "actor_id": "..."}
    """

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import interrupt

    input_guard = input_guard or InputGuard()
    output_guard = output_guard or OutputGuard()
    multimodal_cleaner = multimodal_cleaner or MultimodalCleaner()
    checkpointer = checkpointer or MemorySaver()

    async def input_sanitizer(state: EvaluationState) -> EvaluationState:
        result = input_guard.check(state["raw_inputs"])
        if not result.allowed:
            return {
                **state,
                "error": f"输入被拦截: {result.reason}",
                "status": "error",
                "audit_info": {"triggered_rules": result.triggered_rules},
            }
        return {**state, "status": "data_cleaning"}

    async def data_cleaning(state: EvaluationState) -> EvaluationState:
        if state.get("error"):
            return state
        try:
            cleaned = await multimodal_cleaner.clean_inputs(state["raw_inputs"])
        except Exception as e:
            logger.warning("多模态清洗失败，降级使用原始输入: %s", e)
            cleaned = state["raw_inputs"]
        return {**state, "cleaned_inputs": cleaned, "status": "context_retrieval"}

    async def retrieve_context(state: EvaluationState) -> EvaluationState:
        if state.get("error"):
            return state
        history = await toolkit.get_employee_history(
            state["employee_id"], period=state["period"], limit=5
        )
        kb = await toolkit.query_company_kb(
            query=f"员工评估标准 {state['employee_id']} {state['period']}", top_k=3
        )
        return {**state, "employee_history": history, "company_kb": kb}

    async def build_prompt(state: EvaluationState) -> EvaluationState:
        if state.get("error"):
            return state
        inputs = state.get("cleaned_inputs") or state["raw_inputs"]
        prompt = prompt_loader.render(
            name=prompt_name,
            raw_inputs=inputs,
            employee_history=state.get("employee_history") or [],
            company_kb=state.get("company_kb") or [],
            employee_id=state["employee_id"],
            period=state["period"],
        )
        return {**state, "prompt": prompt}

    async def call_llm(state: EvaluationState) -> EvaluationState:
        if state.get("error"):
            return state
        start = time.time()
        try:
            provider, tier = await model_router.get_provider_with_fallback()
            messages = [
                ChatMessage(role="system", content=state["prompt"]),
                ChatMessage(role="user", content="请根据以上输入生成评估 JSON。"),
            ]
            completion = await provider.chat_completion(
                messages=messages,
                response_format={"type": "json_object"},
            )
            processing_time_ms = int((time.time() - start) * 1000)
            audit_info = {
                "model_name": completion.model,
                "model_tier": tier,
                "confidence_score": 0.0,
                "raw_data_refs": [inp.get("input_id") for inp in state["raw_inputs"]],
                "triggered_rules": ["evidence_first", "dual_view_separation"],
                "processing_time_ms": processing_time_ms,
                "prompt_version": prompt_loader.version(prompt_name),
            }
            return {
                **state,
                "llm_raw_output": completion.content,
                "audit_info": audit_info,
                "status": EvaluationStatus.AI_DRAFTED,
            }
        except Exception as e:
            return {**state, "error": f"LLM 调用失败: {e}", "status": "error"}

    async def parse_output(state: EvaluationState) -> EvaluationState:
        if state.get("error"):
            return state
        raw = state.get("llm_raw_output", "")
        try:
            data = json.loads(raw)
            data["evaluation_id"] = f"EV-{state['period']}-{state['employee_id']}-{uuid.uuid4().hex[:8]}"
            data["employee_id"] = state["employee_id"]
            data["period"] = state["period"]
            data.setdefault("status", EvaluationStatus.AI_DRAFTED)
            audit = data.get("audit", {})
            if state.get("audit_info"):
                audit.update(state["audit_info"])
                evidence_count = sum(
                    len(area.get("evidence", []))
                    for area in data.get("employee_view", {}).get("growth_areas", [])
                )
                audit["confidence_score"] = min(0.95, 0.5 + evidence_count * 0.1)
            data["audit"] = audit
            emp_view = data.get("employee_view", {})
            mgr_view = data.get("manager_view", {})
            emp_result = output_guard.sanitize_employee_view(emp_view)
            mgr_result = output_guard.sanitize_manager_view(mgr_view)

            guard_violations = emp_result.violations + mgr_result.violations
            if guard_violations:
                logger.warning("输出护栏检测到违规: %s", guard_violations)
                audit["output_guard_violations"] = guard_violations
            redacted = emp_result.redacted_entities + mgr_result.redacted_entities
            if redacted:
                audit["redacted_entities"] = redacted

            evaluation = EmployeeEvaluation.model_validate(data)
            return {
                **state,
                "parsed_evaluation": evaluation.model_dump(mode="json"),
                "status": EvaluationStatus.AI_DRAFTED,
            }
        except (json.JSONDecodeError, ValidationError) as e:
            return {**state, "error": f"输出解析失败: {e}", "status": "error"}

    async def review_gate(state: EvaluationState) -> Literal["hr_audit", "manager_review", "rejected"]:
        if state.get("error"):
            return "rejected"
        parsed = state.get("parsed_evaluation")
        if parsed:
            score = parsed.get("overall_score", 100)
            risk_flags = parsed.get("manager_view", {}).get("risk_flags", [])
            has_critical = any(r.get("level") == "critical" for r in risk_flags)
            if score < 60 or has_critical:
                return "hr_audit"
        return "manager_review"

    async def manager_review(state: EvaluationState) -> EvaluationState:
        """
        主管审批中断点：使用 LangGraph 原生 interrupt 暂停执行。
        interrupt() 会抛出 GraphInterrupt，图状态被 checkpointer 持久化。
        恢复时，decision 包含审批结果。
        """
        parsed = state.get("parsed_evaluation") or {}
        parsed["status"] = "manager_review"
        # 暂停并等待人工审批，传递评估摘要供审批人查看
        decision = interrupt(
            {
                "node": "manager_review",
                "evaluation_id": parsed.get("evaluation_id"),
                "employee_id": state["employee_id"],
                "period": state["period"],
                "overall_score": parsed.get("overall_score"),
                "message": "等待主管审批",
            }
        )
        # 恢复后处理审批决策
        action = (decision or {}).get("action", "approve")
        comment = (decision or {}).get("comment", "")
        actor_id = (decision or {}).get("actor_id", "unknown")

        if action == "approve":
            parsed["status"] = "approved"
            parsed["approver_id"] = actor_id
            parsed["manager_review_comment"] = comment
            return {**state, "parsed_evaluation": parsed, "status": "approved"}
        elif action == "reject":
            parsed["status"] = "rejected"
            parsed["manager_review_comment"] = comment
            return {**state, "parsed_evaluation": parsed, "status": "rejected"}
        elif action == "request_hr_review":
            parsed["status"] = "hr_audit"
            parsed["manager_review_comment"] = comment
            return {**state, "parsed_evaluation": parsed, "status": "hr_audit"}
        else:
            return {**state, "status": "error", "error": f"未知审批动作: {action}"}

    async def hr_audit(state: EvaluationState) -> EvaluationState:
        """HR 复核中断点：同样使用原生 interrupt"""
        parsed = state.get("parsed_evaluation") or {}
        parsed["status"] = "hr_audit"
        decision = interrupt(
            {
                "node": "hr_audit",
                "evaluation_id": parsed.get("evaluation_id"),
                "employee_id": state["employee_id"],
                "period": state["period"],
                "overall_score": parsed.get("overall_score"),
                "message": "等待 HR 复核",
            }
        )
        action = (decision or {}).get("action", "approve")
        comment = (decision or {}).get("comment", "")
        actor_id = (decision or {}).get("actor_id", "unknown")

        if action == "approve":
            parsed["status"] = "approved"
            parsed["approver_id"] = actor_id
            parsed["hr_review_comment"] = comment
            return {**state, "parsed_evaluation": parsed, "status": "approved"}
        elif action == "reject":
            parsed["status"] = "rejected"
            parsed["hr_review_comment"] = comment
            return {**state, "parsed_evaluation": parsed, "status": "rejected"}
        else:
            return {**state, "status": "error", "error": f"未知 HR 动作: {action}"}

    async def finalize(state: EvaluationState) -> EvaluationState:
        return state

    builder = StateGraph(EvaluationState)
    builder.add_node("input_sanitizer", input_sanitizer)
    builder.add_node("data_cleaning", data_cleaning)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("build_prompt", build_prompt)
    builder.add_node("call_llm", call_llm)
    builder.add_node("parse_output", parse_output)
    builder.add_node("manager_review", manager_review)
    builder.add_node("hr_audit", hr_audit)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "input_sanitizer")
    builder.add_edge("input_sanitizer", "data_cleaning")
    builder.add_edge("data_cleaning", "retrieve_context")
    builder.add_edge("retrieve_context", "build_prompt")
    builder.add_edge("build_prompt", "call_llm")
    builder.add_edge("call_llm", "parse_output")
    builder.add_conditional_edges(
        "parse_output",
        review_gate,
        {
            "hr_audit": "hr_audit",
            "manager_review": "manager_review",
            "rejected": END,
        },
    )
    builder.add_edge("manager_review", "finalize")
    builder.add_edge("hr_audit", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
