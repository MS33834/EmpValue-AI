"""
LangGraph 评估工作流测试
使用 Mock Provider 避免真实 LLM 调用。
"""

import json
import pytest

from agent.graph import create_evaluation_graph
from agent.prompt_loader import PromptLoader
from agent.tools import AgentToolkit, DummyCompanyKB, DummyMemoryStore
from core.config import Settings
from core.model_router import ModelRouter
from core.providers.base import BaseProvider, ChatCompletion, ChatMessage, ProviderConfig


class MockProvider(BaseProvider):
    """测试用 Mock Provider"""

    def __init__(self, response: dict):
        super().__init__(ProviderConfig(model_name="mock"))
        self.response = response

    def name(self) -> str:
        return "mock"

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        response_format: dict = None,
    ) -> ChatCompletion:
        return ChatCompletion(
            content=json.dumps(self.response, ensure_ascii=False),
            model="mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        )

    async def health_check(self) -> bool:
        return True


class MockModelRouter:
    """测试用 ModelRouter，固定返回 MockProvider"""

    def __init__(self, response: dict):
        self._response = response

    async def get_provider_with_fallback(self):
        return MockProvider(self._response), "L2"


def build_sample_llm_response():
    return {
        "evaluation_id": "EV-2026-W25-E1001",
        "employee_id": "E1001",
        "period": "2026-W25",
        "overall_score": 82.0,
        "employee_view": {
            "summary": "本周你在交付和协作方面都有不错的表现，完成了登录模块重构，并积极参与团队技术分享。",
            "strengths": ["完成登录模块重构", "参与跨团队技术分享"],
            "growth_areas": [
                {
                    "dimension": "业务影响",
                    "score": 75.0,
                    "evidence": ["JIRA-2051 进度 60%，阻塞原因是依赖方接口文档未更新"],
                    "improvement_actions": ["下周主动跟进依赖方，推动 JIRA-2051 完成"],
                }
            ],
            "next_week_focus": ["完成 JIRA-2051", "准备技术分享"],
        },
        "manager_view": {
            "harsh_assessment": "该员工本周交付稳定，但在关键任务推进上存在外部依赖风险，需主管关注并推动解决。",
            "risk_flags": [],
            "roi_analysis": "当前 ROI 中等，需关注关键任务阻塞。",
            "reallocation_suggestion": "保持当前项目，重点解决依赖阻塞。",
            "hidden_issues": ["依赖文档未更新可能影响整体进度"],
        },
        "audit": {
            "model_name": "mock-model",
            "model_tier": "L2",
            "confidence_score": 0.85,
            "raw_data_refs": ["daily-001", "task-001"],
            "triggered_rules": ["evidence_first"],
            "processing_time_ms": 100,
            "prompt_version": "v0.1",
        },
        "status": "ai_drafted",
    }


@pytest.mark.asyncio
async def test_evaluation_graph_happy_path(tmp_path):
    """测试完整评估工作流"""
    response = build_sample_llm_response()
    graph = create_evaluation_graph(
        toolkit=AgentToolkit(DummyMemoryStore(), DummyCompanyKB()),
        model_router=MockModelRouter(response),
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )

    # 创建临时 prompt 文件
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    prompt_dir.joinpath("daily_evaluation.md").write_text(
        "# System Prompt\n\n**版本：** v0.1\n\n{raw_inputs}\n{employee_history}\n{company_kb}\n",
        encoding="utf-8",
    )

    initial_state = {
        "employee_id": "E1001",
        "period": "2026-W25",
        "raw_inputs": [
            {"input_id": "daily-001", "content": "完成了登录模块重构"},
            {"input_id": "task-001", "content": "JIRA-2051 进度 60%"},
        ],
        "messages": [],
    }

    result = await graph.ainvoke(initial_state)
    assert result["status"] == "manager_review"
    assert result["parsed_evaluation"] is not None
    assert result["parsed_evaluation"]["overall_score"] == 82.0


@pytest.mark.asyncio
async def test_evaluation_graph_risk_route_to_hr(tmp_path):
    """高风险用例应进入 hr_audit"""
    response = build_sample_llm_response()
    response["overall_score"] = 55.0
    response["manager_view"]["risk_flags"] = [
        {"level": "critical", "category": "产出", "description": "", "suggested_action": ""}
    ]

    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    prompt_dir.joinpath("daily_evaluation.md").write_text(
        "# System Prompt\n\n**版本：** v0.1\n\n{raw_inputs}\n",
        encoding="utf-8",
    )

    graph = create_evaluation_graph(
        toolkit=AgentToolkit(DummyMemoryStore(), DummyCompanyKB()),
        model_router=MockModelRouter(response),
        prompt_loader=PromptLoader(prompt_dir),
    )

    initial_state = {
        "employee_id": "E1002",
        "period": "2026-W25",
        "raw_inputs": [{"input_id": "daily-002", "content": "处理日常工单"}],
        "messages": [],
    }

    result = await graph.ainvoke(initial_state)
    assert result["status"] == "hr_audit"
