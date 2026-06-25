"""
LLM 回归评估框架单元测试
覆盖 eval/evaluate.py 中的 MockProvider、校验函数、用例评估与端到端 mock 流程。
"""

import json

import pytest

from eval.evaluate import (
    NEGATIVE_WORDS,
    MockProvider,
    build_mock_evaluation,
    build_mock_model_router,
    check_contains,
    check_employee_view_no_negative_words,
    check_evidence_cited,
    check_overall_score_range,
    check_view_keys,
    evaluate_case,
    load_dataset,
    run_case,
    validate_schema,
)
from core.providers.base import ChatMessage, ProviderConfig


class TestBuildMockEvaluation:
    """build_mock_evaluation 生成结构化评估"""

    def test_positive_tone(self):
        result = build_mock_evaluation(score=90, tone="positive", employee_id="E1", period="W1")
        assert result["overall_score"] == 90
        assert result["employee_id"] == "E1"
        assert result["period"] == "W1"
        assert result["status"] == "ai_drafted"
        emp = result["employee_view"]
        assert emp["summary"]
        assert len(emp["strengths"]) >= 1
        assert len(emp["growth_areas"]) >= 1
        assert len(emp["next_week_focus"]) >= 1
        # 正向 tone 不应有 critical 风险
        assert result["manager_view"]["risk_flags"] == []

    def test_negative_tone_has_risk_flags(self):
        result = build_mock_evaluation(score=45, tone="negative", employee_id="E2", period="W2")
        flags = result["manager_view"]["risk_flags"]
        assert len(flags) >= 1
        assert flags[0]["level"] == "high"
        assert result["manager_view"]["hidden_issues"]

    def test_neutral_tone(self):
        result = build_mock_evaluation(score=72, tone="neutral", employee_id="E3", period="W3")
        assert 60 <= result["overall_score"] <= 80
        emp = result["employee_view"]
        assert emp["growth_areas"]

    def test_audit_fields_complete(self):
        result = build_mock_evaluation(score=80, tone="positive", employee_id="E4", period="W4")
        audit = result["audit"]
        for key in ("model_name", "model_tier", "confidence_score", "raw_data_refs",
                    "triggered_rules", "processing_time_ms", "prompt_version"):
            assert key in audit

    def test_keywords_appear_in_summary(self):
        result = build_mock_evaluation(
            score=88, tone="positive", employee_id="E5", period="W5",
            keywords=["主导", "优化"],
        )
        assert "主导" in result["employee_view"]["summary"]

    def test_validates_against_schema(self):
        from schemas import EmployeeEvaluation
        result = build_mock_evaluation(score=80, tone="positive", employee_id="E6", period="W6")
        # 补全 evaluation_id / created_at 等运行时字段
        from datetime import datetime, timezone
        result["evaluation_id"] = "EV-W6-E6-test"
        result["created_at"] = datetime.now(timezone.utc).isoformat()
        result["approved_at"] = None
        result["approver_id"] = None
        EmployeeEvaluation.model_validate(result)


class TestCheckFunctions:
    """独立校验函数"""

    def test_no_negative_words_pass(self):
        ok, msg = check_employee_view_no_negative_words({"summary": "本周表现稳定"})
        assert ok is True

    def test_no_negative_words_fail(self):
        ok, msg = check_employee_view_no_negative_words({"employee_view": {"summary": "表现很差，做事拖沓"}})
        assert ok is False
        assert "很差" in msg

    def test_evidence_cited_pass(self):
        data = {"employee_view": {"growth_areas": [
            {"dimension": "x", "evidence": ["具体证据片段较长"]},
        ]}}
        ok, _ = check_evidence_cited(data)
        assert ok is True

    def test_evidence_cited_missing(self):
        ok, msg = check_evidence_cited({"employee_view": {}})
        assert ok is False

    def test_evidence_too_short(self):
        data = {"employee_view": {"growth_areas": [
            {"dimension": "x", "evidence": ["短"]},
        ]}}
        ok, _ = check_evidence_cited(data)
        assert ok is False

    def test_score_range_pass(self):
        ok, _ = check_overall_score_range({"overall_score": 85}, [80, 90])
        assert ok is True

    def test_score_range_fail(self):
        ok, msg = check_overall_score_range({"overall_score": 50}, [80, 90])
        assert ok is False

    def test_contains_pass(self):
        ok, _ = check_contains({"x": "团队协作"}, ["团队"])
        assert ok is True

    def test_contains_fail(self):
        ok, msg = check_contains({"x": "个人"}, ["团队"])
        assert ok is False
        assert "团队" in msg

    def test_view_keys_pass(self):
        ok, _ = check_view_keys({"employee_view": {"summary": "a", "growth_areas": [], "next_week_focus": []}},
                                ["summary", "growth_areas", "next_week_focus"])
        assert ok is True

    def test_view_keys_fail(self):
        ok, msg = check_view_keys({"employee_view": {"summary": "a"}},
                                  ["summary", "growth_areas"])
        assert ok is False

    def test_validate_schema_valid(self):
        from datetime import datetime, timezone
        result = build_mock_evaluation(score=80, tone="positive", employee_id="E7", period="W7")
        result["evaluation_id"] = "EV-W7-E7-t"
        result["created_at"] = datetime.now(timezone.utc).isoformat()
        result["approved_at"] = None
        result["approver_id"] = None
        ok, _ = validate_schema(result)
        assert ok is True

    def test_validate_schema_invalid(self):
        ok, msg = validate_schema({"overall_score": "not-a-number"})
        assert ok is False


class TestEvaluateCase:
    """evaluate_case 聚合校验"""

    def _make_case(self):
        return {
            "employee_id": "E100",
            "period": "W1",
            "archetype": "star",
            "expected_overall_score_range": [80, 95],
            "expected_contains": ["团队"],
            "expected_view_keys": ["summary", "growth_areas", "next_week_focus"],
        }

    def test_all_pass(self):
        from datetime import datetime, timezone
        eval_result = build_mock_evaluation(score=90, tone="positive", employee_id="E100", period="W1",
                                            keywords=["团队"])
        eval_result["evaluation_id"] = "EV-W1-E100-t"
        eval_result["created_at"] = datetime.now(timezone.utc).isoformat()
        eval_result["approved_at"] = None
        eval_result["approver_id"] = None
        result = evaluate_case(self._make_case(), eval_result)
        assert result["passed"] is True

    def test_skip_contains(self):
        result = evaluate_case(self._make_case(), {"overall_score": 90, "employee_view": {"summary": "a"}}, skip_contains=True)
        # score still checked and fails
        assert result["passed"] is False

    def test_skip_score(self):
        from datetime import datetime, timezone
        eval_result = build_mock_evaluation(score=10, tone="negative", employee_id="E100", period="W1")
        eval_result["evaluation_id"] = "EV-W1-E100-t2"
        eval_result["created_at"] = datetime.now(timezone.utc).isoformat()
        eval_result["approved_at"] = None
        eval_result["approver_id"] = None
        result = evaluate_case(self._make_case(), eval_result, skip_score=True, skip_contains=True)
        assert result["passed"] is True


class TestMockProvider:
    """Mock Provider 行为"""

    def _make_prompt(self, content="本周主导完成核心模块，性能优化提升40%", employee_id="E200", period="W10"):
        raw = [{"input_id": "daily-001", "type": "daily_report", "content": content}]
        return (
            f"## 当前输入\n```json\n{json.dumps(raw, ensure_ascii=False)}\n```\n"
            f"employee_id = {employee_id}\nperiod = {period}\n"
        )

    @pytest.mark.asyncio
    async def test_returns_valid_json(self):
        provider = MockProvider(ProviderConfig(model_name="mock"))
        messages = [ChatMessage(role="system", content=self._make_prompt())]
        completion = await provider.chat_completion(messages)
        data = json.loads(completion.content)
        assert "overall_score" in data
        assert "employee_view" in data
        assert "manager_view" in data
        assert completion.model == "mock-model"

    @pytest.mark.asyncio
    async def test_classifies_positive(self):
        provider = MockProvider(ProviderConfig(model_name="mock"))
        messages = [ChatMessage(role="system", content=self._make_prompt("超额完成，零Bug，主导优化，提前交付"))]
        data = json.loads((await provider.chat_completion(messages)).content)
        assert data["overall_score"] >= 80

    @pytest.mark.asyncio
    async def test_classifies_negative(self):
        provider = MockProvider(ProviderConfig(model_name="mock"))
        messages = [ChatMessage(role="system", content=self._make_prompt("本周任务延期，质量不高，未自测导致崩溃"))]
        data = json.loads((await provider.chat_completion(messages)).content)
        assert data["overall_score"] < 60
        assert data["manager_view"]["risk_flags"]

    @pytest.mark.asyncio
    async def test_health_check(self):
        provider = MockProvider(ProviderConfig(model_name="mock"))
        assert await provider.health_check() is True

    def test_name(self):
        provider = MockProvider(ProviderConfig(model_name="mock"))
        assert provider.name() == "mock/provider"


class TestMockModelRouter:
    """build_mock_model_router 构造"""

    @pytest.mark.asyncio
    async def test_returns_mock_provider(self):
        router = build_mock_model_router(tier="L0")
        provider, tier = await router.get_provider_with_fallback()
        assert provider.name() == "mock/provider"
        assert tier == "L0"


class TestRunCaseEndToEnd:
    """使用 mock router 跑通完整评估图"""

    @pytest.mark.asyncio
    async def test_run_case_with_mock(self):
        case = {
            "employee_id": "E300",
            "period": "W30",
            "raw_inputs": [{"input_id": "d1", "type": "daily_report",
                            "content": "本周主导完成模块重构，优化性能，超额完成目标"}],
        }
        router = build_mock_model_router(tier="L0")
        result = await run_case(case, router)
        assert result.get("status") != "error"
        evaluation = result.get("parsed_evaluation")
        assert evaluation is not None
        assert "employee_view" in evaluation
        assert evaluation["employee_id"] == "E300"


class TestLoadDataset:
    """数据集加载"""

    def test_load_default_dataset(self):
        dataset = load_dataset()
        assert len(dataset) >= 3
        for case in dataset:
            assert "employee_id" in case
            assert "raw_inputs" in case
            assert "expected_overall_score_range" in case
