"""
生成回归测试数据集

用法：
    python backend/eval/generate_dataset.py
输出：
    backend/eval/dataset.json
"""

import json
import random
from pathlib import Path

random.seed(42)

ARCHETYPES = {
    "star": {
        "score_range": (85, 96),
        "keywords": ["超额完成", "主导", "优化", "团队", "高质量"],
        "reports": [
            "本周主导完成用户画像模块重构，性能提升40%，并辅导两名新人完成CR。",
            "提前2天交付Q3核心需求，代码Review通过率100%，客户反馈零Bug。",
            "组织技术分享一次，沉淀最佳实践文档3篇，团队采纳率80%。",
        ],
    },
    "slacker": {
        "score_range": (45, 59),
        "keywords": ["延期", "沟通不及时", "质量不高", "待改进", "未自测"],
        "reports": [
            "本周任务延期2天，日报内容简略，未主动同步阻塞问题。",
            "提交的代码未自测，导致测试环境崩溃一次，修复耗时半天。",
            "会议迟到两次，需求理解反复，输出物与预期差距较大。",
        ],
    },
    "bottleneck": {
        "score_range": (60, 74),
        "keywords": ["加班", "效率", "流程", "阻塞", "熟练度"],
        "reports": [
            "工作投入度高，经常加班，但产出低于预期，关键路径多次被阻塞。",
            "负责模块复杂度评估不足，导致排期延误，需加强技术拆解能力。",
            "沟通响应及时，但代码质量波动大，重构债务累积。",
        ],
    },
    "newcomer": {
        "score_range": (65, 78),
        "keywords": ["学习", "适应", "请教", "成长", "基础"],
        "reports": [
            "入职第二周，已完成环境搭建并独立完成2个简单Bug修复，学习主动性强。",
            "对业务逻辑理解较快，但技术栈熟练度不足，需继续积累。",
            "积极参与团队分享，日报记录详细，成长速度符合预期。",
        ],
    },
    "workaholic": {
        "score_range": (75, 85),
        "keywords": ["完成", "加班", "独立", "沟通少", "稳健"],
        "reports": [
            "本周独立完成全部指派任务，加班较多，但跨团队协作沟通偏少。",
            "输出稳定可靠，但创新性和主动性有提升空间，较少分享经验。",
            "对细节把控严格，交付质量合格，但大包大揽导致团队依赖。",
        ],
    },
}

PERIODS = [f"2026-W{i:02d}" for i in range(20, 30)]


def generate_case(idx: int) -> dict:
    archetype = random.choice(list(ARCHETYPES.keys()))
    info = ARCHETYPES[archetype]
    employee_id = f"E{1000 + idx}"
    period = random.choice(PERIODS)
    report = random.choice(info["reports"])
    expected_score = random.randint(*info["score_range"])

    # 只选择确实出现在报告中的关键词作为 expected_contains，避免 Mock/LLM 无法命中
    present_keywords = [kw for kw in info["keywords"] if kw in report]
    expected_contains = random.sample(present_keywords, k=min(2, len(present_keywords)))

    return {
        "employee_id": employee_id,
        "period": period,
        "archetype": archetype,
        "raw_inputs": [
            {
                "input_id": f"daily-{idx:03d}",
                "type": "daily_report",
                "content": report,
            }
        ],
        "expected_overall_score_range": [expected_score - 5, expected_score + 5],
        "expected_contains": expected_contains,
        "expected_view_keys": ["summary", "growth_areas", "next_week_focus"],
    }


def main(count: int = 50) -> None:
    dataset = [generate_case(i) for i in range(1, count + 1)]
    output = Path(__file__).with_name("dataset.json")
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {count} 条测试用例到 {output}")


if __name__ == "__main__":
    main()
