"""
ModelRouter：硬件探测 + 档位选择 + Provider 路由 + 自动降级
"""

import logging
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from .config import Settings, get_settings
from .providers.base import BaseProvider, ProviderConfig
from .providers.openai_provider import OpenAICompatibleProvider

logger = logging.getLogger(__name__)

ModelTier = Literal["L0", "L1", "L2", "L3"]


@dataclass
class TierInfo:
    """档位信息"""

    tier: ModelTier
    model_name: str
    provider_type: str
    description: str
    min_vram_gb: Optional[float] = None
    min_ram_gb: Optional[float] = None


class ModelRouter:
    """
    模型路由器
    - 根据硬件和配置选择最合适的模型档位
    - 提供 Provider 实例
    - 支持健康检查和自动降级
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._hardware = self._detect_hardware()
        self._tier_map = self._build_tier_map()

    def _build_tier_map(self) -> Dict[ModelTier, TierInfo]:
        return {
            "L0": TierInfo(
                tier="L0",
                model_name=self.settings.cloud_model or self.settings.openai_model,
                provider_type="cloud",
                description="云端大模型，最强推理能力",
            ),
            "L1": TierInfo(
                tier="L1",
                model_name=self.settings.local_model_l1,
                provider_type="local",
                description="本地边缘小模型，纯文本摘要",
                min_vram_gb=0,
                min_ram_gb=4,
            ),
            "L2": TierInfo(
                tier="L2",
                model_name=self.settings.local_model_l2,
                provider_type="local",
                description="本地标准模型，文本+表格分析",
                min_vram_gb=6,
                min_ram_gb=12,
            ),
            "L3": TierInfo(
                tier="L3",
                model_name=self.settings.local_model_l3,
                provider_type="local",
                description="本地旗舰模型，全模态深度推理",
                min_vram_gb=12,
                min_ram_gb=24,
            ),
        }

    @staticmethod
    def _detect_hardware() -> Dict[str, Any]:
        """探测硬件资源"""
        result = {"vram_gb": 0.0, "ram_gb": 0.0, "gpu_count": 0, "gpu_names": []}

        # 内存
        try:
            import psutil

            result["ram_gb"] = psutil.virtual_memory().total / (1024**3)
        except Exception as e:
            logger.warning(f"无法检测内存: {e}")

        # GPU / 显存
        try:
            import torch

            if torch.cuda.is_available():
                result["gpu_count"] = torch.cuda.device_count()
                for i in range(result["gpu_count"]):
                    props = torch.cuda.get_device_properties(i)
                    result["vram_gb"] += props.total_memory / (1024**3)
                    result["gpu_names"].append(props.name)
        except Exception as e:
            logger.debug(f"torch 不可用，尝试 nvidia-smi: {e}")
            #  fallback：尝试 nvidia-smi
            try:
                output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                    text=True,
                )
                total_vram_mb = 0
                for line in output.strip().splitlines():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["gpu_names"].append(parts[0].strip())
                        mem_str = parts[1].strip().replace(" MiB", "").replace(" MB", "")
                        total_vram_mb += int(mem_str)
                result["vram_gb"] = total_vram_mb / 1024
                result["gpu_count"] = len(result["gpu_names"])
            except Exception as e2:
                logger.warning(f"无法检测 GPU: {e2}")

        return result

    def get_recommended_tier(self) -> ModelTier:
        """根据硬件推荐默认档位"""
        if self.settings.model_tier != "auto":
            return self.settings.model_tier  # type: ignore

        # 优先尝试本地高档位
        vram = self._hardware.get("vram_gb", 0)
        ram = self._hardware.get("ram_gb", 0)

        if vram >= self._tier_map["L3"].min_vram_gb and ram >= self._tier_map["L3"].min_ram_gb:
            return "L3"
        if vram >= self._tier_map["L2"].min_vram_gb and ram >= self._tier_map["L2"].min_ram_gb:
            return "L2"
        if ram >= self._tier_map["L1"].min_ram_gb:
            return "L1"

        # 无本地条件则回退云端
        return "L0"

    def get_provider(self, tier: Optional[ModelTier] = None) -> BaseProvider:
        """根据档位返回 Provider 实例"""
        selected_tier = tier or self.get_recommended_tier()
        tier_info = self._tier_map[selected_tier]

        if tier_info.provider_type == "cloud":
            api_key = self.settings.cloud_api_key or self.settings.openai_api_key
            base_url = self.settings.cloud_base_url or self.settings.openai_base_url
            if not api_key:
                logger.warning(
                    f"档位 {selected_tier} 为云端模型，但 cloud_api_key/openai_api_key 未配置，"
                    "调用将失败或回退到本地模型"
                )
            config = ProviderConfig(
                model_name=tier_info.model_name,
                base_url=base_url,
                api_key=api_key,
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_tokens,
            )
        else:
            config = ProviderConfig(
                model_name=tier_info.model_name,
                base_url=self.settings.local_base_url,
                api_key=self.settings.local_api_key,
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_tokens,
            )

        return OpenAICompatibleProvider(config)

    async def get_provider_with_fallback(self) -> tuple[BaseProvider, ModelTier]:
        """
        获取可用 Provider，如果首选不可用则自动降级
        返回 (provider, tier)
        """
        preferred_tier = self.get_recommended_tier()
        order: List[ModelTier] = [preferred_tier]

        # 构造降级顺序
        fallback_order: List[ModelTier] = ["L0", "L3", "L2", "L1"]
        for t in fallback_order:
            if t not in order:
                order.append(t)

        last_error = None
        for tier in order:
            provider = self.get_provider(tier)
            try:
                if await provider.health_check():
                    logger.info(f"ModelRouter 选择档位: {tier}")
                    return provider, tier
            except Exception as e:
                last_error = e
                logger.warning(f"档位 {tier} 健康检查失败: {e}")

        # 如果全部失败，返回首选让调用方在运行时重试/报错
        logger.error(f"所有档位均不可用，返回首选档位: {preferred_tier}, 最后错误: {last_error}")
        return self.get_provider(preferred_tier), preferred_tier

    def hardware_report(self) -> Dict[str, Any]:
        """返回硬件探测报告"""
        return {
            **self._hardware,
            "recommended_tier": self.get_recommended_tier(),
        }
