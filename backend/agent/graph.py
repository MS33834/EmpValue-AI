"""
LangGraph 评估工作流
"""

import json
import time
import uuid
from typing import Any, Dict, List, Literal, Optional

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from core.guards import InputGuard, OutputGuard
from core.model_router import ModelRouter
from core.providers.base import ChatMessage
from schemas import EmployeeEvaluation

from .prompt_loader import PromptLoader
from .state import EvaluationState
from .tools import AgentToolkit


def create_evaluation_graph(
    toolkit: AgentToolkit,
    model_router: ModelRouter,
    prompt_loader: PromptLoader,
    prompt_name: str = "daily_evaluation",
    input_guard: Optional[InputGuard] = None,
    output_guard: Optional[OutputGuard] = None,
):
    """创建评估工作流图"""

    input_guard = input_guard or InputGuard()
    output_guard = output_guard or OutputGuard()

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
            "status": "ai_processing",
            "cleaned_inputs": state["raw_inputs"],
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
                "status": "ai_drafted",
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
            # 补充必要字段
            data.setdefault("evaluation_id", f"EV-{state['period']}-{state['employee_id']}-{uuid.uuid4().hex[:8]}")
            data.setdefault("employee_id", state["employee_id"])
            data.setdefault("period", state["period"])
            data.setdefault("status", "ai_drafted")

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
            output_guard.sanitize_employee_view(emp_view)
            output_guard.sanitize_manager_view(mgr_view)

            evaluation = EmployeeEvaluation.model_validate(data)
            return {
                **state,
                "parsed_evaluation": evaluation.model_dump(mode="json"),
                "status": "ai_drafted",
            }
        except (json.JSONDecodeError, ValidationError) as e:
            return {**state, "error": f"输出解析失败: {e}", "status": "error"}

    async def manager_review_gate(state: EvaluationState) -> Literal["hr_audit", "approved", "rejected"]:
        """
        模拟主管审批节点
        实际运行时由 API 层写入 manager_review_comment 并恢复图执行
        """
        if state.get("error"):
            return "rejected"
        # 高风险或低分自动进入 HR 复核
        parsed = state.get("parsed_evaluation")
        if parsed:
            score = parsed.get("overall_score", 100)
            risk_flags = parsed.get("manager_view", {}).get("risk_flags", [])
            has_critical = any(r.get("level") == "critical" for r in risk_flags)
            if score < 60 or has_critical:
                return "hr_audit"
        # 默认通过，进入 approved（实际应等待主管操作，此处为简化）
        return "approved"

    async def finalize(state: EvaluationState) -> EvaluationState:
        """最终状态节点"""
        final_status = state.get("status")
        if final_status == "error":
            return state
        # 保留上游节点设置的状态（approved 或 hr_audit 复核完成后的状态）
        if final_status in ("approved", "hr_audit"):
            return state
        return {**state, "status": "approved"}

    async def hr_audit(state: EvaluationState) -> EvaluationState:
        """HR 复核节点（简化版）"""
        return {**state, "status": "hr_audit"}

    # 构建图
    builder = StateGraph(EvaluationState)
    builder.add_node("input_sanitizer", input_sanitizer)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("build_prompt", build_prompt)
    builder.add_node("call_llm", call_llm)
    builder.add_node("parse_output", parse_output)
    builder.add_node("hr_audit", hr_audit)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "input_sanitizer")
    builder.add_edge("input_sanitizer", "retrieve_context")
    builder.add_edge("retrieve_context", "build_prompt")
    builder.add_edge("build_prompt", "call_llm")
    builder.add_edge("call_llm", "parse_output")
    builder.add_conditional_edges(
        "parse_output",
        manager_review_gate,
        {
            "hr_audit": "hr_audit",
            "approved": "finalize",
            "rejected": END,
        },
    )
    builder.add_edge("hr_audit", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()
