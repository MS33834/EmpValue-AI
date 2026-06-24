"""
FastAPI 路由定义
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    AppState,
    get_app_state,
    get_approval_service,
    get_audit_service,
    get_evaluation_service,
)
from auth.rbac import Role, can_access, get_client_ip, get_current_user_id, require_role
from core.database import get_db
from core.tracing import tracer
from services.approval_service import ApprovalService
from services.audit_service import AuditService
from services.evaluation_service import EvaluationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# 评估异步任务状态存储（生产环境应替换为 Redis / 数据库）
job_store: Dict[str, Dict[str, Any]] = {}


def _update_job(job_id: str, update: Dict[str, Any]) -> None:
    """更新任务状态"""
    job = job_store.get(job_id)
    if job:
        job.update(update)
        job["updated_at"] = datetime.now(timezone.utc).isoformat()


async def _run_evaluation_job(
    job_id: str,
    employee_id: str,
    period: str,
    raw_inputs: List[Dict[str, Any]],
    app_state: AppState,
) -> None:
    """后台执行评估图，并更新 job_store"""
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        eval_service = EvaluationService(session)
        audit_service = AuditService(session)
        graph = app_state.get_graph(eval_service)
        initial_state = {
            "employee_id": employee_id,
            "period": period,
            "raw_inputs": raw_inputs,
            "messages": [],
        }

        try:
            with tracer.trace(
                name="create_evaluation_async",
                evaluation_id=None,
                employee_id=employee_id,
                metadata={"period": period, "input_count": len(raw_inputs), "job_id": job_id},
            ) as trace:
                with tracer.span(trace, "run_graph", input_data=initial_state):
                    result = await graph.ainvoke(initial_state)

                if result.get("error"):
                    trace.update(metadata={**trace.metadata, "error": result["error"]})
                    logger.error("评估图执行失败 job_id=%s: %s", job_id, result["error"])
                    _update_job(
                        job_id,
                        {
                            "status": "failed",
                            "error": "评估处理失败，请查看服务端日志",
                        },
                    )
                    return

                evaluation = result.get("parsed_evaluation")
                if evaluation:
                    await eval_service.create_evaluation(evaluation)
                    memory_payload = {
                        "period": period,
                        "summary": evaluation.get("employee_view", {}).get("summary", ""),
                        "overall_score": evaluation.get("overall_score"),
                        "status": evaluation.get("status"),
                    }
                    await eval_service.add_memory(employee_id, memory_payload)
                    await app_state.memory_store.add_memory(employee_id, memory_payload)
                    trace.update(
                        output=evaluation,
                        metadata={
                            **trace.metadata,
                            "model_tier": evaluation.get("audit", {}).get("model_tier"),
                            "overall_score": evaluation.get("overall_score"),
                        },
                    )
                    await audit_service.log(
                        actor_id="system",
                        action="create_evaluation_async",
                        evaluation_id=evaluation.get("evaluation_id"),
                        employee_id=employee_id,
                        details={"period": period, "model_tier": evaluation.get("audit", {}).get("model_tier")},
                    )
                    _update_job(
                        job_id,
                        {
                            "status": "completed",
                            "evaluation": evaluation,
                        },
                    )
                else:
                    _update_job(job_id, {"status": "failed", "error": "未生成评估结果"})
        except Exception as e:
            logger.exception("评估处理失败 job_id=%s", job_id)
            _update_job(job_id, {"status": "failed", "error": "评估处理失败，请查看服务端日志"})


@router.post("/inputs", response_model=Dict[str, Any])
async def create_input(
    payload: Dict[str, Any],
    request: Request,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    audit_service: AuditService = Depends(get_audit_service),
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """提交员工日报/任务进度等原始输入"""
    employee_id = payload.get("employee_id")
    period = payload.get("period")
    content = payload.get("content")

    if not employee_id or not period or not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="employee_id、period、content 必填",
        )

    input_id = payload.get("input_id") or f"input-{uuid.uuid4().hex[:8]}"
    raw = await eval_service.create_raw_input(
        {
            "input_id": input_id,
            "employee_id": employee_id,
            "period": period,
            "type": payload.get("type", "daily_report"),
            "content": content,
            "attachments": payload.get("attachments", []),
        }
    )

    await audit_service.log(
        actor_id=employee_id,
        action="create_input",
        employee_id=employee_id,
        details={"input_id": input_id, "period": period, "type": raw.type},
        ip_address=get_client_ip(request),
    )

    return {
        "input_id": raw.input_id,
        "employee_id": raw.employee_id,
        "period": raw.period,
        "type": raw.type,
        "content": raw.content,
        "created_at": raw.created_at.isoformat(),
    }


@router.get("/inputs/{input_id}")
async def get_input(
    input_id: str,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """查询原始输入"""
    raw = await eval_service.get_raw_input(input_id)
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="输入不存在")
    return {
        "input_id": raw.input_id,
        "employee_id": raw.employee_id,
        "period": raw.period,
        "type": raw.type,
        "content": raw.content,
        "attachments": raw.attachments,
        "created_at": raw.created_at.isoformat(),
    }


@router.post("/evaluations", response_model=Dict[str, Any])
async def create_evaluation(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    app_state: AppState = Depends(get_app_state),
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """异步触发一次员工评估，立即返回 job_id"""
    employee_id = payload.get("employee_id")
    period = payload.get("period")
    raw_inputs = payload.get("raw_inputs", [])

    if not employee_id or not period:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="employee_id 和 period 必填",
        )

    # 确保用户存在
    await eval_service.ensure_user_exists(employee_id, role="employee")

    # 持久化传入的 raw_inputs（如果尚未存在）
    for inp in raw_inputs:
        existing = await eval_service.get_raw_input(inp.get("input_id"))
        if not existing:
            await eval_service.create_raw_input(
                {
                    "input_id": inp.get("input_id") or f"input-{uuid.uuid4().hex[:8]}",
                    "employee_id": employee_id,
                    "period": period,
                    "type": inp.get("type", "daily_report"),
                    "content": inp.get("content", ""),
                    "attachments": inp.get("attachments", []),
                }
            )

    # 如果没有传入 raw_inputs，从数据库拉取
    if not raw_inputs:
        inputs = await eval_service.list_raw_inputs(employee_id=employee_id, period=period)
        raw_inputs = [
            {"input_id": i.input_id, "type": i.type, "content": i.content}
            for i in inputs
        ]

    job_id = f"job-{uuid.uuid4().hex[:12]}"
    job_store[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "employee_id": employee_id,
        "period": period,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    background_tasks.add_task(
        _run_evaluation_job,
        job_id,
        employee_id,
        period,
        raw_inputs,
        app_state,
    )

    return {"job_id": job_id, "status": "pending"}


@router.get("/evaluations/jobs/{job_id}")
async def get_evaluation_job(
    job_id: str,
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """查询异步评估任务状态"""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation(
    evaluation_id: str,
    request: Request,
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
    eval_service: EvaluationService = Depends(get_evaluation_service),
):
    """获取评估结果，按角色过滤可见字段"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    if role == Role.EMPLOYEE:
        current_user_id = get_current_user_id(request)
        if evaluation.employee_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该评估")

    data = {
        "evaluation_id": evaluation.evaluation_id,
        "employee_id": evaluation.employee_id,
        "period": evaluation.period,
        "overall_score": evaluation.overall_score,
        "status": evaluation.status,
        "created_at": evaluation.created_at.isoformat(),
        "approved_at": evaluation.approved_at.isoformat() if evaluation.approved_at else None,
        "approver_id": evaluation.approver_id,
    }

    if can_access(role, "employee_view"):
        data["employee_view"] = evaluation.employee_view
    if can_access(role, "manager_view"):
        data["manager_view"] = evaluation.manager_view
    if can_access(role, "audit"):
        data["audit"] = evaluation.audit

    return data


@router.get("/evaluations/{evaluation_id}/employee-view")
async def get_employee_view(
    evaluation_id: str,
    request: Request,
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
    eval_service: EvaluationService = Depends(get_evaluation_service),
):
    """员工可见视图"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    if role == Role.EMPLOYEE:
        current_user_id = get_current_user_id(request)
        if evaluation.employee_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该评估")
    return {
        "evaluation_id": evaluation.evaluation_id,
        "employee_id": evaluation.employee_id,
        "period": evaluation.period,
        "employee_view": evaluation.employee_view,
    }


@router.get("/evaluations/{evaluation_id}/manager-view")
async def get_manager_view(
    evaluation_id: str,
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
    eval_service: EvaluationService = Depends(get_evaluation_service),
):
    """管理/HR 可见视图"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")
    return {
        "evaluation_id": evaluation.evaluation_id,
        "employee_id": evaluation.employee_id,
        "period": evaluation.period,
        "manager_view": evaluation.manager_view,
    }


@router.post("/evaluations/{evaluation_id}/approve")
async def approve_evaluation(
    evaluation_id: str,
    payload: Dict[str, Any],
    request: Request,
    app_state: AppState = Depends(get_app_state),
    eval_service: EvaluationService = Depends(get_evaluation_service),
    approval_service: ApprovalService = Depends(get_approval_service),
    audit_service: AuditService = Depends(get_audit_service),
    session: AsyncSession = Depends(get_db),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """审批通过评估"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    current_status = evaluation.status
    actor_id = get_current_user_id(request)
    comment = payload.get("comment")

    try:
        new_status = await approval_service.transition(
            evaluation_id=evaluation_id,
            current_status=current_status,
            action="approve",
            actor_id=actor_id,
            actor_role=role.value,
            comment=comment,
        )
        await eval_service.update_status(
            evaluation_id=evaluation_id,
            new_status=new_status,
            approver_id=actor_id,
        )
        await audit_service.log(
            actor_id=actor_id,
            action="approve_evaluation",
            evaluation_id=evaluation_id,
            details={"from_status": current_status, "to_status": new_status},
            ip_address=get_client_ip(request),
        )
        await session.commit()
        return {"evaluation_id": evaluation_id, "status": new_status}
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations/{evaluation_id}/reject")
async def reject_evaluation(
    evaluation_id: str,
    payload: Dict[str, Any],
    request: Request,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    approval_service: ApprovalService = Depends(get_approval_service),
    audit_service: AuditService = Depends(get_audit_service),
    session: AsyncSession = Depends(get_db),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """驳回评估"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    current_status = evaluation.status
    actor_id = get_current_user_id(request)
    comment = payload.get("comment")

    try:
        new_status = await approval_service.transition(
            evaluation_id=evaluation_id,
            current_status=current_status,
            action="reject",
            actor_id=actor_id,
            actor_role=role.value,
            comment=comment,
        )
        await eval_service.update_status(
            evaluation_id=evaluation_id,
            new_status=new_status,
        )
        await audit_service.log(
            actor_id=actor_id,
            action="reject_evaluation",
            evaluation_id=evaluation_id,
            details={"from_status": current_status, "to_status": new_status, "comment": comment},
            ip_address=get_client_ip(request),
        )
        await session.commit()
        return {"evaluation_id": evaluation_id, "status": new_status}
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations/{evaluation_id}/feedback")
async def create_feedback(
    evaluation_id: str,
    payload: Dict[str, Any],
    request: Request,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    audit_service: AuditService = Depends(get_audit_service),
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """员工反馈/申诉"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    if role == Role.EMPLOYEE:
        current_user_id = get_current_user_id(request)
        if evaluation.employee_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该评估")

    content = payload.get("content")
    feedback_type = payload.get("type", "feedback")
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content 必填",
        )

    actor_id = get_current_user_id(request)
    feedback_id = payload.get("feedback_id") or f"FB-{uuid.uuid4().hex[:8]}"
    feedback = await eval_service.create_feedback(
        {
            "feedback_id": feedback_id,
            "evaluation_id": evaluation_id,
            "employee_id": evaluation.employee_id,
            "type": feedback_type,
            "content": content,
        }
    )

    await audit_service.log(
        actor_id=actor_id,
        action="create_feedback",
        evaluation_id=evaluation_id,
        employee_id=evaluation.employee_id,
        details={"feedback_id": feedback_id, "type": feedback_type},
        ip_address=get_client_ip(request),
    )

    return {
        "feedback_id": feedback.feedback_id,
        "evaluation_id": feedback.evaluation_id,
        "type": feedback.type,
        "content": feedback.content,
        "created_at": feedback.created_at.isoformat(),
    }


@router.get("/evaluations/{evaluation_id}/audit-logs")
async def get_evaluation_audit_logs(
    evaluation_id: str,
    audit_service: AuditService = Depends(get_audit_service),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """获取评估审计日志"""
    logs = await audit_service.get_logs(evaluation_id=evaluation_id)
    return {
        "evaluation_id": evaluation_id,
        "logs": [
            {
                "log_id": log.log_id,
                "actor_id": log.actor_id,
                "action": log.action,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


@router.get("/manager/pending-approvals")
async def get_pending_approvals(
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """主管待审批列表（包含 ai_drafted 与 manager_review）"""
    pending = []
    for status in ("ai_drafted", "manager_review"):
        pending.extend(await eval_service.list_evaluations(status=status, limit=200))
    return {
        "pending": [
            {
                "evaluation_id": e.evaluation_id,
                "employee_id": e.employee_id,
                "period": e.period,
                "status": e.status,
                "overall_score": e.overall_score,
                "created_at": e.created_at.isoformat(),
            }
            for e in pending
        ]
    }


@router.get("/manager/dashboard")
async def get_manager_dashboard(
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """主管工作台概览"""
    pending = []
    for status in ("ai_drafted", "manager_review"):
        pending.extend(await eval_service.list_evaluations(status=status, limit=200))
    approved = await eval_service.list_evaluations(status="approved", limit=10)
    return {
        "pending_count": len(pending),
        "pending": [
            {
                "evaluation_id": e.evaluation_id,
                "employee_id": e.employee_id,
                "period": e.period,
                "overall_score": e.overall_score,
                "created_at": e.created_at.isoformat(),
            }
            for e in pending[:10]
        ],
        "recent_approved": [
            {
                "evaluation_id": e.evaluation_id,
                "employee_id": e.employee_id,
                "period": e.period,
                "overall_score": e.overall_score,
                "approved_at": e.approved_at.isoformat() if e.approved_at else None,
            }
            for e in approved[:5]
        ],
    }


@router.get("/hr/audit-queue")
async def get_hr_audit_queue(
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.HR, Role.ADMIN)),
):
    """HR 复核队列"""
    audits = await eval_service.list_evaluations(status="hr_audit", limit=200)
    return {
        "pending": [
            {
                "evaluation_id": e.evaluation_id,
                "employee_id": e.employee_id,
                "period": e.period,
                "overall_score": e.overall_score,
                "created_at": e.created_at.isoformat(),
            }
            for e in audits
        ]
    }


@router.post("/evaluations/{evaluation_id}/request-hr-review")
async def request_hr_review(
    evaluation_id: str,
    payload: Dict[str, Any],
    request: Request,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    approval_service: ApprovalService = Depends(get_approval_service),
    audit_service: AuditService = Depends(get_audit_service),
    session: AsyncSession = Depends(get_db),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """主管提交 HR 复核"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    current_status = evaluation.status
    actor_id = get_current_user_id(request)
    comment = payload.get("comment")

    try:
        new_status = await approval_service.transition(
            evaluation_id=evaluation_id,
            current_status=current_status,
            action="request_hr_review",
            actor_id=actor_id,
            actor_role=role.value,
            comment=comment,
        )
        await eval_service.update_status(evaluation_id=evaluation_id, new_status=new_status)
        await audit_service.log(
            actor_id=actor_id,
            action="request_hr_review",
            evaluation_id=evaluation_id,
            details={"from_status": current_status, "to_status": new_status, "comment": comment},
            ip_address=get_client_ip(request),
        )
        await session.commit()
        return {"evaluation_id": evaluation_id, "status": new_status}
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations/{evaluation_id}/appeal")
async def appeal_evaluation(
    evaluation_id: str,
    payload: Dict[str, Any],
    request: Request,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    approval_service: ApprovalService = Depends(get_approval_service),
    audit_service: AuditService = Depends(get_audit_service),
    session: AsyncSession = Depends(get_db),
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """员工对 approved/rejected 评估提出申诉，回到 manager_review"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    current_status = evaluation.status
    actor_id = get_current_user_id(request)
    comment = payload.get("comment")

    if current_status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有 approved 或 rejected 状态的评估可以申诉",
        )

    try:
        new_status = await approval_service.transition(
            evaluation_id=evaluation_id,
            current_status=current_status,
            action="appeal",
            actor_id=actor_id,
            actor_role=role.value,
            comment=comment,
        )
        await eval_service.update_status(evaluation_id=evaluation_id, new_status=new_status)
        await audit_service.log(
            actor_id=actor_id,
            action="appeal_evaluation",
            evaluation_id=evaluation_id,
            details={"from_status": current_status, "to_status": new_status, "comment": comment},
            ip_address=get_client_ip(request),
        )
        await session.commit()
        return {"evaluation_id": evaluation_id, "status": new_status}
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations/{evaluation_id}/re-evaluate")
async def re_evaluate(
    evaluation_id: str,
    payload: Dict[str, Any],
    request: Request,
    app_state: AppState = Depends(get_app_state),
    eval_service: EvaluationService = Depends(get_evaluation_service),
    audit_service: AuditService = Depends(get_audit_service),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """基于反馈或申诉重新运行评估，生成新的 AI 草稿"""
    evaluation = await eval_service.get_evaluation(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估不存在")

    # 收集原始输入与反馈
    raw_inputs = [
        {"input_id": i.input_id, "type": i.type, "content": i.content}
        for i in await eval_service.list_raw_inputs(
            employee_id=evaluation.employee_id, period=evaluation.period
        )
    ]
    if not raw_inputs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未找到该周期的原始输入，无法重新评估",
        )

    feedback_items = payload.get("feedback", [])
    if not isinstance(feedback_items, list):
        feedback_items = [feedback_items]

    graph = app_state.get_graph(eval_service)
    initial_state = {
        "employee_id": evaluation.employee_id,
        "period": evaluation.period,
        "raw_inputs": raw_inputs,
        "messages": [],
    }

    result = await graph.ainvoke(initial_state)
    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="评估处理失败",
        )

    new_eval = result.get("parsed_evaluation")
    if not new_eval:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重新评估未返回结果",
        )

    # 覆盖旧 evaluation_id，保留历史审计
    new_eval["evaluation_id"] = evaluation_id
    await eval_service.update_evaluation(evaluation_id=evaluation_id, evaluation_data=new_eval)
    await audit_service.log(
        actor_id=payload.get("actor_id", "system"),
        action="re_evaluate",
        evaluation_id=evaluation_id,
        details={
            "previous_status": evaluation.status,
            "new_status": new_eval["status"],
            "feedback_count": len(feedback_items),
        },
        ip_address=get_client_ip(request),
    )

    return {"evaluation_id": evaluation_id, "status": new_eval["status"], "feedback_processed": len(feedback_items)}


@router.get("/employees/{employee_id}/dashboard")
async def get_employee_dashboard(
    employee_id: str,
    request: Request,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """员工个人成长看板"""
    if role == Role.EMPLOYEE:
        employee_id = get_current_user_id(request)
    evaluations = await eval_service.list_evaluations(
        employee_id=employee_id, status="approved", limit=10
    )
    latest = evaluations[0] if evaluations else None
    return {
        "employee_id": employee_id,
        "latest_evaluation": (
            {
                "evaluation_id": latest.evaluation_id,
                "period": latest.period,
                "overall_score": latest.overall_score,
                "employee_view": latest.employee_view,
            }
            if latest
            else None
        ),
        "history_count": len(evaluations),
    }


@router.get("/employees/{employee_id}/history")
async def get_employee_history(
    employee_id: str,
    request: Request,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """跨周期能力演进"""
    if role == Role.EMPLOYEE:
        employee_id = get_current_user_id(request)
    evaluations = await eval_service.list_evaluations(
        employee_id=employee_id, status="approved", limit=50
    )
    return {
        "employee_id": employee_id,
        "evaluations": [
            {
                "evaluation_id": e.evaluation_id,
                "period": e.period,
                "overall_score": e.overall_score,
                "employee_view": {
                    "summary": e.employee_view.get("summary", ""),
                    "growth_areas": e.employee_view.get("growth_areas", []),
                },
                "created_at": e.created_at.isoformat(),
            }
            for e in evaluations
        ],
    }


@router.post("/teams/{team_id}/analytics")
async def get_team_analytics(
    team_id: str,
    payload: Optional[Dict[str, Any]] = None,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """团队分析（管理端）
    请求体示例：{"members": ["E1001", "E1002", "E1003"]}
    """
    payload = payload or {}
    members = payload.get("members", [])
    if not members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="members 列表必填",
        )
    analytics = await eval_service.get_team_analytics(members)
    return {"team_id": team_id, **analytics}


@router.get("/teams/{team_id}/analytics")
async def get_team_analytics_get(
    team_id: str,
    members: str,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """团队分析（GET 版本，members 以逗号分隔）
    示例：/teams/team-1/analytics?members=E1001,E1002
    """
    member_list = [m.strip() for m in members.split(",") if m.strip()]
    if not member_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="members 参数必填",
        )
    analytics = await eval_service.get_team_analytics(member_list)
    return {"team_id": team_id, **analytics}


@router.get("/admin/model-status")
async def get_model_status(
    app_state: AppState = Depends(get_app_state),
    role: Role = Depends(require_role(Role.ADMIN)),
):
    """获取模型状态与推荐档位"""
    return app_state.model_router.hardware_report()


@router.post("/admin/model-switch")
async def switch_model_tier(
    payload: Dict[str, Any],
    app_state: AppState = Depends(get_app_state),
    role: Role = Depends(require_role(Role.ADMIN)),
):
    """手动切换模型档位"""
    tier = payload.get("tier")
    valid_tiers = ["auto", "L0", "L1", "L2", "L3"]
    if tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tier 必须是其中之一: {valid_tiers}",
        )
    app_state.settings.model_tier = tier
    return {"tier": tier, "recommended": app_state.model_router.get_recommended_tier()}


@router.get("/admin/audit-logs")
async def get_admin_audit_logs(
    request: Request,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    audit_service: AuditService = Depends(get_audit_service),
    role: Role = Depends(require_role(Role.ADMIN)),
):
    """管理端审计日志查询，支持按操作人、动作筛选与分页"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 20
    return await audit_service.list_logs(
        actor_id=actor_id,
        action=action,
        page=page,
        page_size=page_size,
    )
