"""
ModelRouter 单元测试
主要测试档位选择逻辑，避免真实网络调用。
"""

import pytest

from core.config import Settings
from core.model_router import ModelRouter


def test_cloud_fallback_when_no_local_ram():
    """内存极低时应回退云端 L0"""
    settings = Settings(model_tier="auto")
    router = ModelRouter(settings)
    # 强制覆盖硬件检测结果为无资源
    router._hardware = {"vram_gb": 0, "ram_gb": 1, "gpu_count": 0, "gpu_names": []}
    assert router.get_recommended_tier() == "L0"


def test_l1_when_min_ram():
    """仅有 4GB 内存时选择 L1"""
    settings = Settings(model_tier="auto")
    router = ModelRouter(settings)
    router._hardware = {"vram_gb": 0, "ram_gb": 4, "gpu_count": 0, "gpu_names": []}
    assert router.get_recommended_tier() == "L1"


def test_l2_when_modest_gpu():
    """有 8GB 显存 + 16GB 内存时选择 L2"""
    settings = Settings(model_tier="auto")
    router = ModelRouter(settings)
    router._hardware = {"vram_gb": 8, "ram_gb": 16, "gpu_count": 1, "gpu_names": ["RTX 4060"]}
    assert router.get_recommended_tier() == "L2"


def test_l3_when_high_end_gpu():
    """有 24GB 显存 + 32GB 内存时选择 L3"""
    settings = Settings(model_tier="auto")
    router = ModelRouter(settings)
    router._hardware = {"vram_gb": 24, "ram_gb": 32, "gpu_count": 1, "gpu_names": ["RTX 4090"]}
    assert router.get_recommended_tier() == "L3"


def test_manual_tier_override():
    """手动设置档位时优先使用手动设置"""
    settings = Settings(model_tier="L1")
    router = ModelRouter(settings)
    router._hardware = {"vram_gb": 24, "ram_gb": 32, "gpu_count": 1, "gpu_names": []}
    assert router.get_recommended_tier() == "L1"


def test_provider_config_for_cloud():
    """L0 档位应生成云端 Provider 配置"""
    settings = Settings(
        model_tier="L0",
        openai_api_key="fake-key",
        openai_model="gpt-4o-mini",
    )
    router = ModelRouter(settings)
    provider = router.get_provider("L0")
    assert provider.config.model_name == "gpt-4o-mini"
    assert provider.config.base_url == settings.openai_base_url


def test_provider_config_for_local():
    """L2 档位应生成本地 Provider 配置"""
    settings = Settings(model_tier="L2", local_base_url="http://localhost:1234/v1")
    router = ModelRouter(settings)
    provider = router.get_provider("L2")
    assert provider.config.model_name == settings.local_model_l2
    assert provider.config.base_url == "http://localhost:1234/v1"
