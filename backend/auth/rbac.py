"""
RBAC（基于角色的访问控制）
从请求头解析当前用户身份与角色。
注意：当前为演示模式，身份由前端 header 传递。
生产环境应替换为 JWT / Session 解析，禁止信任客户端 header。
"""

import logging
from enum import Enum

from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)


class Role(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR = "hr"
    ADMIN = "admin"


# 角色可访问的评估视图
VIEW_PERMISSIONS = {
    Role.EMPLOYEE: ["employee_view"],
    Role.MANAGER: ["employee_view", "manager_view", "audit"],
    Role.HR: ["employee_view", "manager_view", "audit"],
    Role.ADMIN: ["employee_view", "manager_view", "audit"],
}


def can_access(role: Role, view: str) -> bool:
    return view in VIEW_PERMISSIONS.get(role, [])


def get_current_user_role(request: Request) -> Role:
    """
    从请求头解析当前用户角色。
    生产环境应替换为 JWT / Session 解析。
    """
    role_header = request.headers.get("x-user-role", "")
    try:
        return Role(role_header.lower()) if role_header else Role.EMPLOYEE
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色: {role_header}",
        )


def get_current_user_id(request: Request) -> str:
    """从请求头解析当前用户 ID。生产环境应从 token 提取。"""
    return request.headers.get("x-user-id") or "anonymous"


def get_client_ip(request: Request) -> str:
    """提取客户端真实 IP（支持反向代理）"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_role(*allowed_roles: Role):
    """FastAPI 依赖：要求特定角色"""

    def checker(role: Role = Depends(get_current_user_role)):
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return role

    return checker

