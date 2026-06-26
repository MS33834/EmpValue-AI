"""
全局测试配置
"""
import shutil
import tempfile

import pytest

from core.config import get_settings


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """测试环境配置：开启演示模式、使用临时向量库目录、设置测试 JWT 密钥。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_demo_mode", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "test-only-jwt-secret-do-not-use-in-production")

    tmp_dir = tempfile.mkdtemp(prefix="chroma_test_")
    monkeypatch.setattr(settings, "vector_store_dir", tmp_dir)

    yield tmp_dir

    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clear_global_state():
    """每个测试前后清理全局 job_store / thread_store，避免状态泄漏。"""
    from api import routes as routes_module

    routes_module.job_store.clear()
    if hasattr(routes_module, "thread_store"):
        routes_module.thread_store.clear()
    yield
    routes_module.job_store.clear()
    if hasattr(routes_module, "thread_store"):
        routes_module.thread_store.clear()
