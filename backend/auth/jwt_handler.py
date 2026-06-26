"""
JWT Token 生成与校验
注意：本模块不依赖 auth.rbac，避免循环导入。role 以字符串形式传递。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from core.config import get_settings

logger = logging.getLogger(__name__)


def _ensure_secret_key(settings) -> str:
    key = settings.jwt_secret_key
    if not key:
        raise RuntimeError(
            "JWT_SECRET_KEY 未配置，请在环境变量中设置强随机密钥后再启动服务"
        )
    return key


def create_access_token(
    user_id: str,
    role: str,
    name: str = "",
    expires_minutes: Optional[int] = None,
) -> str:
    """生成 JWT access token"""
    settings = get_settings()
    secret_key = _ensure_secret_key(settings)
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload: Dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "name": name,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """解码并校验 JWT，返回 payload 或 None"""
    settings = get_settings()
    try:
        secret_key = _ensure_secret_key(settings)
        return jwt.decode(token, secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("JWT 校验失败: %s", e)
        return None


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization header 提取 Bearer token"""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None
