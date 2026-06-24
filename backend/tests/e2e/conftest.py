"""
E2E 测试配置
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """为 e2e 测试添加标记"""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
