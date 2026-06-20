"""
LLM 输出回归评估脚本
用于对模型生成的评估结果做结构化校验与规则检查。
"""

import json
import re
import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import EmployeeEvaluation


NEGATIVE_WORDS = [
    "差", "懒", "慢", "拖沓", "消极", "不合格", "无能", "没用",
    "糟糕", "失败", "失职", "敷衍", "逃避", "推卸",
]


def load_dataset(path: str = None):
    if path is None:
        path = Path(__file__).parent / "dataset.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_employee_view_no_negative_words(eval_result: dict) -> tuple[bool, str]:
    employee_view = json.dumps(eval_result.get("employee_view", {}), ensure_ascii=False)
    hits = [w for w in NEGATIVE_WORDS if w in employee_view]
    if hits:
        return False, f"员工视图出现负面词: {hits}"
    return True, "OK"


def check_evidence_cited(eval_result: dict) -> tuple[bool, str]:
    growth_areas = eval_result.get("employee_view", {}).get("growth_areas", [])
    if not growth_areas:
        return False, "缺少 growth_areas"
    for area in growth_areas:
        evidence = area.get("evidence", [])
        if not evidence or all(len(e.strip()) < 10 for e in evidence):
            return False, f"维度 {area.get('dimension')} 的证据引用不足"
    return True, "OK"


def check_manager_view_has_risk_flags(eval_result: dict, expected: bool) -> tuple[bool, str]:
    risk_flags = eval_result.get("manager_view", {}).get("risk_flags", [])
    has_flags = len(risk_flags) > 0
    if expected and not has_flags:
        return False, "期望有风险标记，但未识别到"
    if not expected and has_flags:
        return False, f"不期望有风险标记，但识别到 {len(risk_flags)} 个"
    return True, "OK"


def check_overall_score_range(eval_result: dict, expected_range: list) -> tuple[bool, str]:
    score = eval_result.get("overall_score")
    low, high = expected_range
    if score is None or not (low <= score <= high):
        return False, f"overall_score {score} 不在期望区间 [{low}, {high}]"
    return True, "OK"


def validate_schema(eval_result: dict) -> tuple[bool, str]:
    try:
        EmployeeEvaluation.model_validate(eval_result)
        return True, "OK"
    except ValidationError as e:
        return False, f"Schema 校验失败: {e}"


def evaluate_case(case: dict, eval_result: dict) -> dict:
    checks = case["expected_checks"]
    results = {
        "case_id": case["case_id"],
        "schema_valid": validate_schema(eval_result),
        "no_negative_words": check_employee_view_no_negative_words(eval_result),
        "evidence_cited": check_evidence_cited(eval_result),
        "risk_flags_match": check_manager_view_has_risk_flags(
            eval_result, checks["manager_view_has_risk_flags"]
        ),
        "score_in_range": check_overall_score_range(
            eval_result, checks["overall_score_range"]
        ),
    }
    results["passed"] = all(r[0] for r in results.values() if isinstance(r, tuple))
    return results


def print_report(results: list[dict]):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"\n评估结果: {passed}/{total} 通过")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"\n[{status}] {r['case_id']}")
        for key, value in r.items():
            if key in ("case_id", "passed"):
                continue
            ok, msg = value
            print(f"  {key}: {'OK' if ok else msg}")


if __name__ == "__main__":
    dataset = load_dataset()
    print(f"加载了 {len(dataset)} 条回归用例")
    # TODO: 接入真实 LLM 推理后，将结果传入 evaluate_case
    # 当前仅展示数据集结构与检查逻辑
    for case in dataset:
        print(f"- {case['case_id']}: {case['employee_id']} ({len(case['raw_inputs'])} 条输入)")
