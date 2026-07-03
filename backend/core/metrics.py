"""
Prometheus 指标收集。

业务代码只管调下面的埋点函数，label 拼装和命名集中在这里管，避免散落到各处拼写出错。
setup_metrics(app) 把 prometheus_client 的 ASGI 应用挂到 /metrics，不走鉴权，方便 Prometheus 直接抓。

指标统一以 empvalue_ 为前缀。
"""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

# 业务指标定义

# 评估总数（按终态 status 与模型档位 model_tier 维度统计）
EVALUATIONS_TOTAL = Counter(
    "empvalue_evaluations_total",
    "完成的评估总数",
    ["status", "model_tier"],
)

# 评估耗时分布（按模型档位统计，单位：秒）
EVALUATION_DURATION_SECONDS = Histogram(
    "empvalue_evaluation_duration_seconds",
    "单次评估耗时（秒）",
    ["model_tier"],
)

# 审批状态流转次数（记录 action 与 from/to 状态，便于分析审批漏斗）
APPROVAL_TRANSITIONS_TOTAL = Counter(
    "empvalue_approval_transitions_total",
    "审批状态流转次数",
    ["action", "from_status", "to_status"],
)

# 反馈/申诉总数（按类型统计：feedback / appeal）
FEEDBACK_TOTAL = Counter(
    "empvalue_feedback_total",
    "员工反馈与申诉数",
    ["type"],
)

# LLM 调用次数（按模型档位与调用状态统计：success / error / timeout 等）
LLM_REQUESTS_TOTAL = Counter(
    "empvalue_llm_requests_total",
    "LLM 调用次数",
    ["model_tier", "status"],
)

# 当前活跃评估任务数（异步评估 job 的实时存量，Gauge 可升可降）
ACTIVE_JOBS = Gauge(
    "empvalue_active_jobs",
    "当前活跃评估任务数",
)


# 便捷埋点函数


def record_evaluation(status: str, model_tier: str) -> None:
    """记录一次评估完成（status 为评估终态，model_tier 为模型档位）。"""
    EVALUATIONS_TOTAL.labels(status=status, model_tier=model_tier).inc()


def observe_evaluation_duration(duration: float, model_tier: str) -> None:
    """观测一次评估耗时（duration 单位：秒）。"""
    EVALUATION_DURATION_SECONDS.labels(model_tier=model_tier).observe(duration)


def record_approval_transition(action: str, from_status: str, to_status: str) -> None:
    """记录一次审批状态流转。"""
    APPROVAL_TRANSITIONS_TOTAL.labels(
        action=action, from_status=from_status, to_status=to_status
    ).inc()


def record_feedback(feedback_type: str) -> None:
    """记录一次反馈/申诉（feedback_type: feedback / appeal）。"""
    FEEDBACK_TOTAL.labels(type=feedback_type).inc()


def record_llm_request(model_tier: str, status: str) -> None:
    """记录一次 LLM 调用（status: success / error / timeout 等）。"""
    LLM_REQUESTS_TOTAL.labels(model_tier=model_tier, status=status).inc()


def set_active_jobs(n: int) -> None:
    """设置当前活跃评估任务数。"""
    ACTIVE_JOBS.set(n)


# ASGI 挂载


def setup_metrics(app: FastAPI) -> None:
    """
    把 prometheus_client 的 ASGI 应用挂到 FastAPI 的 /metrics 路径。

    挂载的子应用不走 FastAPI 路由依赖注入（不要求鉴权），
    可直接供 Prometheus 抓取。中间件（CORS / 请求体限制）仍生效。
    """
    app.mount("/metrics", make_asgi_app())
