"""
认证相关路由：登录、注册、当前用户信息、刷新 token
"""

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_handler import create_access_token, decode_access_token, extract_bearer_token
from auth.password import hash_password, verify_password
from auth.rbac import Role, get_client_ip, get_current_user_id, get_current_user_role
from api.deps import get_audit_service
from core.config import get_settings
from core.database import get_db
from services.audit_service import AuditService
from services.evaluation_service import EvaluationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="employee")
    department: str | None = None


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
):
    """邮箱 + 密码登录，返回 JWT"""
    eval_service = EvaluationService(session)
    user = await eval_service.get_user_by_email(payload.email)
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )
    if not verify_password(payload.password, user.password_hash):
        await audit_service.log(
            actor_id=user.user_id,
            action="login_failed",
            details={"email": payload.email},
            ip_address=get_client_ip(request),
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    try:
        role = Role(user.role)
    except ValueError:
        role = Role.EMPLOYEE

    token = create_access_token(user.user_id, role.value, name=user.name)
    await audit_service.log(
        actor_id=user.user_id,
        action="login_success",
        details={"email": payload.email, "role": role.value},
        ip_address=get_client_ip(request),
    )
    await session.commit()
    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        name=user.name,
        role=role.value,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
):
    """注册新用户（仅允许注册 employee/manager/hr，admin 需后台创建）"""
    if payload.role not in ("employee", "manager", "hr"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不允许注册该角色",
        )

    eval_service = EvaluationService(session)

    existing_email = await eval_service.get_user_by_email(payload.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被注册",
        )
    existing_id = await eval_service.get_user(payload.user_id)
    if existing_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户 ID 已存在",
        )

    user = await eval_service.create_user(
        {
            "user_id": payload.user_id,
            "name": payload.name,
            "email": payload.email,
            "role": payload.role,
            "department": payload.department,
            "password_hash": hash_password(payload.password),
        }
    )

    try:
        role = Role(user.role)
    except ValueError:
        role = Role.EMPLOYEE

    token = create_access_token(user.user_id, role.value, name=user.name)
    await audit_service.log(
        actor_id=user.user_id,
        action="register",
        details={"email": payload.email, "role": role.value},
        ip_address=get_client_ip(request),
    )
    await session.commit()
    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        name=user.name,
        role=role.value,
    )


@router.get("/me", response_model=Dict[str, Any])
async def me(
    request: Request,
    role: Role = Depends(get_current_user_role),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """获取当前登录用户信息"""
    eval_service = EvaluationService(session)
    user = await eval_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "department": user.department,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """使用有效 token 换取新 token（续期）"""
    auth_header = request.headers.get("authorization")
    token = extract_bearer_token(auth_header)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    eval_service = EvaluationService(session)
    user = await eval_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    try:
        role = Role(user.role)
    except ValueError:
        role = Role.EMPLOYEE

    new_token = create_access_token(user.user_id, role.value, name=user.name)
    return TokenResponse(
        access_token=new_token,
        user_id=user.user_id,
        name=user.name,
        role=role.value,
    )


@router.post("/seed-demo-users", response_model=Dict[str, Any])
async def seed_demo_users(
    session: AsyncSession = Depends(get_db),
):
    """初始化演示账号（仅当库中无该邮箱时创建）。仅在演示模式下可用。"""
    settings = get_settings()
    if not settings.auth_demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="演示模式未开启，此接口不可用。请在开发环境设置 AUTH_DEMO_MODE=true",
        )
    eval_service = EvaluationService(session)
    demo_accounts = [
        ("E1001", "张三（员工）", "employee@empvalue.ai", "employee", "研发部"),
        ("M001", "李四（主管）", "manager@empvalue.ai", "manager", "研发部"),
        ("HR001", "王五（HR）", "hr@empvalue.ai", "hr", "人力资源部"),
        ("ADMIN001", "赵六（管理员）", "admin@empvalue.ai", "admin", "信息技术部"),
    ]
    default_password = "empvalue123"
    created = []
    for user_id, name, email, role, dept in demo_accounts:
        existing = await eval_service.get_user_by_email(email)
        if existing:
            continue
        await eval_service.create_user(
            {
                "user_id": user_id,
                "name": name,
                "email": email,
                "role": role,
                "department": dept,
                "password_hash": hash_password(default_password),
            }
        )
        created.append(email)
    await session.commit()
    return {
        "created": created,
        "note": "演示账号已初始化，生产环境请关闭演示模式并修改默认密码",
    }
