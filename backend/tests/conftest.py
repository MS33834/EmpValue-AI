"""
全局测试配置
"""
import shutil
import tempfile
from pathlib import Path

import pytest

from core.config import get_settings


@pytest.fixture(autouse=True)
def temp_vector_store(monkeypatch):
    """每个测试使用独立的临时向量库目录，避免 ChromaDB embedding function 冲突。"""
    tmp_dir = tempfile.mkdtemp(prefix="chroma_test_")
    monkeypatch.setattr(get_settings(), "vector_store_dir", tmp_dir)

    yield tmp_dir

    # 清理临时向量库
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
