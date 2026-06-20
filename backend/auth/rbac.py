"""
RBAC（基于角色的访问控制）
简化版：定义角色与视图权限，FastAPI 依赖使用。
"""

from enum import Enum
from functools import wraps
from typing import List

from fastapi import Depends, HTTPException, status


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


def get_current_user_role() -> Role:
    """
    占位符：实际应从 JWT / Session 中解析当前用户角色
    默认返回 MANAGER 便于测试
    """
    return Role.MANAGER


def require_role(*allowed_roles: Role):
    """FastAPI 依赖：要求特定角色"""

    def checker():
        # 动态读取，便于测试时 patch
        from auth.rbac import get_current_user_role as _get_current_user_role

        role = _get_current_user_role()
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return role

    return checker
