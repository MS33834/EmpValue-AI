"""
数据集批量生成脚本（M1 遗漏项补完）

从模板批量生成 eval/dataset.json 测试用例，覆盖 5 类员工画像、多部门、多职级、
不同分数档位。与 eval/generate_dataset.py 互补：本脚本聚焦“可 import 的生成函数 +
命令行入口”，且默认只生成到内存返回，仅在显式指定 --output 时才落盘，避免覆盖
现有 eval/dataset.json。

用法：
    # 仅生成到内存并打印摘要（不写文件，安全）
    python -m scripts.generate_dataset --count 50

    # 生成并写入指定路径
    python -m scripts.generate_dataset --count 50 --output eval/dataset.json

可 import 用法：
    from scripts.generate_dataset import generate_dataset
    cases = generate_dataset(count=50)
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List

# 固定随机种子，保证同一 count 下生成结果可复现，便于回归对拍
random.seed(42)

# 5 类员工画像：star/steady/slacker/newhire/bottleneck
# 每类包含分数档位、信号关键词、日报模板
ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "star": {
        # 上界取 95 而非 96，确保 score±5 恒落在 [0,100] 且宽度恒为 10
        "score_range": (85, 95),
        "keywords": ["超额完成", "主导", "优化", "团队", "高质量"],
        "reports": [
            "本周主导完成用户画像模块重构，性能提升40%，并辅导两名新人完成CR。",
            "提前2天交付Q3核心需求，代码Review通过率100%，客户反馈零Bug。",
            "组织技术分享一次，沉淀最佳实践文档3篇，团队采纳率80%。",
        ],
    },
    "steady": {
        "score_range": (75, 85),
        "keywords": ["完成", "独立", "稳健", "交付", "可靠"],
        "reports": [
            "本周独立完成全部指派任务，交付质量稳定可靠，但跨团队协作沟通偏少。",
            "输出稳定可靠，对细节把控严格，交付质量合格，较少主动分享经验。",
            "按期完成既定需求，代码风格统一，但创新性和主动性有提升空间。",
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
    "newhire": {
        "score_range": (65, 78),
        "keywords": ["学习", "适应", "请教", "成长", "基础"],
        "reports": [
            "入职第二周，已完成环境搭建并独立完成2个简单Bug修复，学习主动性强。",
            "对业务逻辑理解较快，但技术栈熟练度不足，主动请教老员工。",
            "积极参与团队分享，日报记录详细，成长速度符合预期。",
        ],
    },
    "bottleneck": {
        "score_range": (60, 74),
        "keywords": ["加班", "效率", "流程", "阻塞", "熟练度"],
        "reports": [
            "工作投入度高，经常加班，但产出低于预期，关键路径多次被阻塞。",
            "负责模块复杂度评估不足，导致排期延误，需加强技术拆解能力。",
            "沟通响应及时，但代码质量波动大，重构债务累积影响整体效率。",
        ],
    },
}

# 多部门：覆盖研发/产品/数据/市场/设计，体现跨部门多样性
DEPARTMENTS: List[str] = ["研发中心", "产品中心", "数据团队", "市场部", "设计中心"]

# 多职级：覆盖执行层 P5-P8 与管理线 M1-M2
LEVELS: List[str] = ["P5", "P6", "P7", "P8", "M1", "M2"]

# 评估周期：2026-W20 ~ 2026-W29 共 10 周
PERIODS: List[str] = [f"2026-W{i:02d}" for i in range(20, 30)]

# 员工视图固定应包含的字段（与 eval 框架 check_view_keys 对齐）
EXPECTED_VIEW_KEYS: List[str] = ["summary", "growth_areas", "next_week_focus"]

# 画像顺序固定，配合 idx 取模实现“轮转抽样”，保证 count>=5 时 5 类画像全部出现
ARCHETYPE_ORDER: List[str] = list(ARCHETYPES.keys())


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    """将分数限制在 [low, high] 区间，避免越界。"""
    return max(low, min(high, value))


def generate_case(idx: int) -> Dict[str, Any]:
    """
    生成单条测试用例。

    - archetype 按 idx 轮转选取，保证 5 类画像在批量生成时全覆盖；
    - department / level / period / report / score 随机抽样，体现多样性；
    - expected_contains 只取报告中真实命中的关键词，避免 Mock/LLM 无法命中；
    - expected_overall_score_range = [score-5, score+5]，并 clamp 到 [0, 100]。
    """
    # 轮转选取画像，确保 5 类均出现（count>=5 时统计覆盖）
    archetype = ARCHETYPE_ORDER[idx % len(ARCHETYPE_ORDER)]
    info = ARCHETYPES[archetype]

    employee_id = f"E{1000 + idx}"
    period = random.choice(PERIODS)
    department = random.choice(DEPARTMENTS)
    level = random.choice(LEVELS)
    report = random.choice(info["reports"])

    # 分数档位：在 archetype score_range 内随机取一个中心分
    expected_score = random.randint(*info["score_range"])
    low = _clamp(expected_score - 5)
    high = _clamp(expected_score + 5)

    # 只选择确实出现在报告中的关键词作为 expected_contains
    present_keywords = [kw for kw in info["keywords"] if kw in report]
    expected_contains = random.sample(
        present_keywords, k=min(2, len(present_keywords))
    )

    return {
        "employee_id": employee_id,
        "period": period,
        "archetype": archetype,
        "department": department,
        "level": level,
        "raw_inputs": [
            {
                "input_id": f"daily-{idx:03d}",
                "type": "daily_report",
                "content": report,
            }
        ],
        "expected_overall_score_range": [low, high],
        "expected_contains": expected_contains,
        "expected_view_keys": list(EXPECTED_VIEW_KEYS),
    }


def generate_dataset(count: int = 50) -> List[Dict[str, Any]]:
    """
    批量生成 count 条测试用例，返回用例列表（不写文件）。

    本函数为可 import 的核心入口，默认仅生成到内存返回，避免覆盖现有
    eval/dataset.json。如需落盘，请使用命令行 --output 参数或自行写文件。

    参数：
        count: 生成用例数量，默认 50。
    返回：
        长度为 count 的用例列表，每条用例字段见 generate_case。
    """
    if count < 0:
        raise ValueError(f"count 不能为负数: {count}")
    return [generate_case(idx) for idx in range(1, count + 1)]


def main() -> None:
    """命令行入口：解析参数，按需生成并落盘。"""
    parser = argparse.ArgumentParser(
        description="从模板批量生成 eval/dataset.json 测试用例"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="生成用例数量，默认 50",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "输出文件路径（如 eval/dataset.json）。"
            "未指定时仅生成到内存并打印摘要，不写文件，避免覆盖现有数据集。"
        ),
    )
    args = parser.parse_args()

    dataset = generate_dataset(count=args.count)

    # 统计画像覆盖情况，便于人工核对多样性
    archetype_counts: Dict[str, int] = {}
    for case in dataset:
        archetype_counts[case["archetype"]] = archetype_counts.get(case["archetype"], 0) + 1

    if args.output:
        output_path = Path(args.output)
        # 若父目录不存在则创建，避免因目录缺失写入失败
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"已生成 {len(dataset)} 条用例到 {output_path}")
        print(f"画像分布: {archetype_counts}")
    else:
        # 默认只生成到内存，不落盘，避免覆盖现有 eval/dataset.json
        print(f"已生成 {len(dataset)} 条用例（仅内存，未写文件）")
        print(f"画像分布: {archetype_counts}")
        print("如需落盘，请加 --output <path> 参数")


if __name__ == "__main__":
    main()
