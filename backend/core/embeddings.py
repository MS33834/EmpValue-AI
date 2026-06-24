"""
Embedding 服务：基于 OpenAI 兼容接口的统一 embedding 客户端。
支持云端（OpenAI / DeepSeek / 阿里云百炼等）和本地模型。
"""

import logging
from typing import List, Optional

from openai import AsyncOpenAI

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """OpenAI 兼容 embedding 客户端"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        api_key = self.settings.embedding_api_key or self.settings.cloud_api_key or self.settings.openai_api_key
        base_url = self.settings.embedding_base_url or self.settings.cloud_base_url or self.settings.openai_base_url
        self.model = self.settings.embedding_model
        self.dimensions = self.settings.embedding_dimensions

        kwargs: dict = {}
        if base_url:
            kwargs["base_url"] = base_url
        # 允许无 API key 初始化（测试/本地启动），实际调用时会再校验
        kwargs["api_key"] = api_key or "dummy-key"
        self._has_real_key = bool(api_key)
        self.client = AsyncOpenAI(**kwargs)

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """对文本列表进行 embedding，返回向量列表"""
        if not texts:
            return []
        if not self._has_real_key:
            raise RuntimeError(
                "未配置 embedding_api_key / cloud_api_key / openai_api_key，无法生成真实向量"
            )
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=list(texts),
            )
            vectors = [item.embedding for item in response.data]
            # 校验维度
            for i, vec in enumerate(vectors):
                if len(vec) != self.dimensions:
                    logger.warning(
                        f"embedding 维度不一致: expected={self.dimensions}, got={len(vec)} for text[{i}]"
                    )
            return vectors
        except Exception as e:
            logger.error(f"embedding 调用失败: {e}")
            raise

    async def embed_query(self, text: str) -> List[float]:
        """对单条查询文本进行 embedding"""
        vectors = await self.embed([text])
        return vectors[0]
