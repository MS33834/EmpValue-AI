#!/usr/bin/env python3
"""
EmpValue-AI 生产就绪检查脚本

检查生产部署前的安全清单，打印 PASS/FAIL/WARN 报告，
退出码 0 表示全部通过（允许 WARN），1 表示存在 FAIL 项。

检查项：
    1. AUTH_DEMO_MODE 是否关闭（避免身份伪造）
    2. JWT_SECRET_KEY 是否已修改（非空且非默认占位值）
    3. DATABASE_URL 是否非 SQLite（生产建议 PostgreSQL，SQLite 仅 WARN）
    4. MODEL_TIER 是否显式设置（auto 仅 WARN）

用法：
    cd backend
    python -m scripts.check_prod_readiness
    python scripts/check_prod_readiness.py
"""

import sys
from pathlib import Path
from typing import Optional

# 兼容 `python scripts/xxx.py` 直接执行：将 backend 根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Settings, get_settings


# 已知的 JWT_SECRET_KEY 默认/占位值（小写匹配），生产环境必须修改
DEFAULT_JWT_SECRETS = {
    "",
    "change-me",
    "your-secret-key",
    "change-this-to-a-strong-random-secret",
    "secret",
    "jwt-secret-key",
    "changeme",
}


def _check_auth_demo_mode(settings: Settings) -> dict:
    """检查演示模式是否关闭。"""
    if settings.auth_demo_mode:
        return {
            "name": "auth_demo_mode",
            "status": "FAIL",
            "message": "AUTH_DEMO_MODE 已开启，生产环境必须关闭（避免身份伪造）",
        }
    return {
        "name": "auth_demo_mode",
        "status": "PASS",
        "message": "AUTH_DEMO_MODE 已关闭",
    }


def _check_jwt_secret(settings: Settings) -> dict:
    """检查 JWT 密钥是否已配置为非默认值。"""
    key = settings.jwt_secret_key
    if key is None or key.strip() == "" or key.strip().lower() in DEFAULT_JWT_SECRETS:
        return {
            "name": "jwt_secret_key",
            "status": "FAIL",
            "message": "JWT_SECRET_KEY 未设置或为默认占位值，生产环境必须配置强随机密钥",
        }
    return {
        "name": "jwt_secret_key",
        "status": "PASS",
        "message": "JWT_SECRET_KEY 已配置为非默认值",
    }


def _check_database_url(settings: Settings) -> dict:
    """检查数据库连接：生产建议 PostgreSQL，SQLite 给 WARN 但可继续。"""
    url = (settings.database_url or "").lower()
    if "sqlite" in url:
        return {
            "name": "database_url",
            "status": "WARN",
            "message": "DATABASE_URL 为 SQLite，生产环境建议使用 PostgreSQL",
        }
    return {
        "name": "database_url",
        "status": "PASS",
        "message": "DATABASE_URL 已使用非 SQLite 数据库",
    }


def _check_model_tier(settings: Settings) -> dict:
    """检查模型档位是否显式设置（auto 仅 WARN）。"""
    if settings.model_tier == "auto":
        return {
            "name": "model_tier",
            "status": "WARN",
            "message": "MODEL_TIER 为 auto，建议生产环境显式指定档位（L0/L1/L2/L3）",
        }
    return {
        "name": "model_tier",
        "status": "PASS",
        "message": f"MODEL_TIER 已显式设置为 {settings.model_tier}",
    }


def check_readiness(settings: Optional[Settings] = None) -> dict:
    """
    执行生产就绪检查。

    参数：
        settings: 可选的 Settings 实例；不传时读取全局 get_settings()。
                  若生产环境守护校验器拦截实例化（demo_mode 在生产开启），
                  则直接返回该项 FAIL。

    返回：
        dict {
            checks: [{name, status, message}, ...],
            all_passed: bool  # 无任何 FAIL 即为 True（WARN 不影响）
        }
    """
    if settings is None:
        try:
            settings = get_settings()
        except ValueError as e:
            # 生产环境守护触发：AUTH_DEMO_MODE 在生产环境开启
            checks = [
                {
                    "name": "auth_demo_mode",
                    "status": "FAIL",
                    "message": f"生产环境守护拦截: {e}",
                }
            ]
            return {"checks": checks, "all_passed": False}

    checks = [
        _check_auth_demo_mode(settings),
        _check_jwt_secret(settings),
        _check_database_url(settings),
        _check_model_tier(settings),
    ]
    all_passed = not any(c["status"] == "FAIL" for c in checks)
    return {"checks": checks, "all_passed": all_passed}


def print_report(result: dict) -> None:
    """打印生产就绪报告。"""
    print("=" * 60)
    print("EmpValue-AI 生产就绪检查")
    print("=" * 60)
    for check in result["checks"]:
        status = check["status"]
        if status == "PASS":
            mark = "✅"
        elif status == "FAIL":
            mark = "❌"
        else:
            mark = "⚠️ "
        print(f"{mark} {status:<5} [{check['name']}] {check['message']}")
    print("-" * 60)
    if result["all_passed"]:
        print("结论: ✅ 全部关键项通过（允许存在 WARN）")
    else:
        print("结论: ❌ 存在 FAIL 项，不具备生产就绪条件")
    print("=" * 60)


def main(argv: Optional[list[str]] = None) -> int:
    """命令行入口。返回 0 表示全部通过，1 表示存在 FAIL。"""
    result = check_readiness()
    print_report(result)
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
