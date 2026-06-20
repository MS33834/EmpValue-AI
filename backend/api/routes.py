"""
FastAPI 路由定义
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agent.tools import DummyCompanyKB, DummyMemoryStore
from api.deps import AppState, get_app_state
from auth.rbac import Role, can_access, require_role
from schemas import EmployeeEvaluation
from services.approval_service import ApprovalService
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1")


@router.post("/evaluations", response_model=Dict[str, Any])
async def create_evaluation(
    payload: Dict[str, Any],
    app_state: AppState = Depends(get_app_state),
):
    """触发一次员工评估"""
    employee_id = payload.get("employee_id")
    period = payload.get("period")
    raw_inputs = payload.get("raw_inputs", [])

    if not employee_id or not period:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="employee_id 和 period 必填",
        )

    graph = app_state.get_graph()
    initial_state = {
        "employee_id": employee_id,
        "period": period,
        "raw_inputs": raw_inputs,
        "messages": [],
    }

    result = await graph.ainvoke(initial_state)

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    evaluation = result.get("parsed_evaluation")
    if evaluation:
        app_state.audit_service.log(
            actor_id="system",
            action="create_evaluation",
            evaluation_id=evaluation.get("evaluation_id"),
            employee_id=employee_id,
            details={"period": period, "model_tier": evaluation.get("audit", {}).get("model_tier")},
        )

    return {
        "evaluation": evaluation,
        "status": result.get("status"),
    }


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation(
    evaluation_id: str,
    role: Role = Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """
    获取评估结果
    实际应从数据库查询并按角色过滤视图
    当前返回占位说明
    """
    return {
        "evaluation_id": evaluation_id,
        "message": "请连接数据库实现持久化查询",
        "accessible_views": [v for v in ["employee_view", "manager_view", "audit"] if can_access(role, v)],
    }


@router.post("/evaluations/{evaluation_id}/approve")
async def approve_evaluation(
    evaluation_id: str,
    payload: Dict[str, Any],
    app_state: AppState = Depends(get_app_state),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """审批通过评估"""
    current_status = payload.get("current_status", "ai_drafted")
    actor_id = payload.get("actor_id", "unknown")
    comment = payload.get("comment")

    try:
        new_status = app_state.approval_service.transition(
            evaluation_id=evaluation_id,
            current_status=current_status,
            action="approve",
            actor_id=actor_id,
            actor_role=role.value,
            comment=comment,
        )
        app_state.audit_service.log(
            actor_id=actor_id,
            action="approve_evaluation",
            evaluation_id=evaluation_id,
            details={"from_status": current_status, "to_status": new_status},
        )
        return {"evaluation_id": evaluation_id, "status": new_status}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations/{evaluation_id}/reject")
async def reject_evaluation(
    evaluation_id: str,
    payload: Dict[str, Any],
    app_state: AppState = Depends(get_app_state),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """驳回评估"""
    current_status = payload.get("current_status", "ai_drafted")
    actor_id = payload.get("actor_id", "unknown")
    comment = payload.get("comment")

    try:
        new_status = app_state.approval_service.transition(
            evaluation_id=evaluation_id,
            current_status=current_status,
            action="reject",
            actor_id=actor_id,
            actor_role=role.value,
            comment=comment,
        )
        app_state.audit_service.log(
            actor_id=actor_id,
            action="reject_evaluation",
            evaluation_id=evaluation_id,
            details={"from_status": current_status, "to_status": new_status, "comment": comment},
        )
        return {"evaluation_id": evaluation_id, "status": new_status}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/evaluations/{evaluation_id}/audit-logs")
async def get_evaluation_audit_logs(
    evaluation_id: str,
    app_state: AppState = Depends(get_app_state),
    role: Role = Depends(require_role(Role.MANAGER, Role.HR, Role.ADMIN)),
):
    """获取评估审计日志"""
    logs = app_state.audit_service.get_logs(evaluation_id=evaluation_id)
    return {"evaluation_id": evaluation_id, "logs": [log.model_dump(mode="json") for log in logs]}


@router.get("/admin/model-status")
async def get_model_status(
    app_state: AppState = Depends(get_app_state),
    role: Role = Depends(require_role(Role.ADMIN)),
):
    """获取模型状态与推荐档位"""
    return app_state.model_router.hardware_report()
