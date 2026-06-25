"""
脚本辅助测试
覆盖 seed_demo 演示数据 Schema 校验、run_mock_evaluations 端到端流程。
"""

import pytest

from data.loader import ProfileLoader
from eval.evaluate import build_mock_model_router
from schemas import EmployeeEvaluation


class TestSeedDemoData:
    """seed_demo.py 中 SAMPLE_EVALUATION 的数据完整性"""

    def _load_sample(self):
        from scripts.seed_demo import SAMPLE_EVALUATION
        return SAMPLE_EVALUATION

    def test_sample_evaluation_validates(self):
        """演示评估数据通过 Schema 校验"""
        from datetime import datetime, timezone
        data = dict(self._load_sample())
        # 补全运行时字段
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("approved_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("approver_id", "M001")
        EmployeeEvaluation.model_validate(data)

    def test_sample_has_dual_views(self):
        data = self._load_sample()
        assert data["employee_view"]["summary"]
        assert data["employee_view"]["strengths"]
        assert data["employee_view"]["growth_areas"]
        assert data["manager_view"]["harsh_assessment"]
        assert data["manager_view"]["risk_flags"]

    def test_sample_evidence_non_empty(self):
        data = self._load_sample()
        for area in data["employee_view"]["growth_areas"]:
            assert area["evidence"], f"维度 {area['dimension']} 缺少证据"
            assert area["improvement_actions"]

    def test_sample_audit_complete(self):
        data = self._load_sample()
        audit = data["audit"]
        for key in ("model_name", "model_tier", "confidence_score",
                    "raw_data_refs", "triggered_rules", "processing_time_ms",
                    "prompt_version"):
            assert key in audit, f"audit 缺少 {key}"


class TestRunMockEvaluations:
    """run_mock_evaluations 端到端：5 类画像跑通评估图"""

    @pytest.mark.asyncio
    async def test_all_profiles_produce_evaluation(self):
        """每个画像的最新周期都能生成有效评估"""
        from agent.graph import create_evaluation_graph
        from agent.prompt_loader import PromptLoader
        from agent.tools import AgentToolkit, DummyCompanyKB, DummyMemoryStore

        loader = ProfileLoader()
        toolkit = AgentToolkit(DummyMemoryStore(), DummyCompanyKB())
        router = build_mock_model_router(tier="L0")
        graph = create_evaluation_graph(toolkit, router, PromptLoader())

        for profile in loader.list_profiles():
            employee_id = profile["employee_id"]
            period = loader.get_latest_period(employee_id)
            raw_inputs = loader.get_inputs(employee_id, period)

            result = await graph.ainvoke({
                "employee_id": employee_id,
                "period": period,
                "raw_inputs": raw_inputs,
                "messages": [],
            })
            assert not result.get("error"), f"{profile['name']} 评估失败: {result.get('error')}"
            evaluation = result.get("parsed_evaluation")
            assert evaluation is not None, f"{profile['name']} 未生成评估"
            assert evaluation["employee_id"] == employee_id
            assert 0 <= evaluation["overall_score"] <= 100

    @pytest.mark.asyncio
    async def test_star_profile_scores_higher_than_slacker(self):
        """明星型得分应高于摸鱼型"""
        from agent.graph import create_evaluation_graph
        from agent.prompt_loader import PromptLoader
        from agent.tools import AgentToolkit, DummyCompanyKB, DummyMemoryStore

        loader = ProfileLoader()
        toolkit = AgentToolkit(DummyMemoryStore(), DummyCompanyKB())
        router = build_mock_model_router(tier="L0")
        graph = create_evaluation_graph(toolkit, router, PromptLoader())

        scores = {}
        for archetype in ("star", "slacker"):
            profile = next(p for p in loader.list_profiles() if p["archetype"] == archetype)
            employee_id = profile["employee_id"]
            period = loader.get_latest_period(employee_id)
            raw_inputs = loader.get_inputs(employee_id, period)
            result = await graph.ainvoke({
                "employee_id": employee_id, "period": period,
                "raw_inputs": raw_inputs, "messages": [],
            })
            scores[archetype] = result["parsed_evaluation"]["overall_score"]

        assert scores["star"] > scores["slacker"], \
            f"明星型({scores['star']})应高于摸鱼型({scores['slacker']})"
