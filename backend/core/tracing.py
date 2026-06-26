"""
Langfuse 可观测性集成
追踪 Agent 执行全链路：输入、Prompt、模型调用、输出、审批状态。
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Optional

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class NoOpTrace:
    """当 Langfuse 未配置时的空实现"""

    def __init__(self):
        self.metadata = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def span(self, *args, **kwargs):
        return NoOpTrace()

    def update(self, *args, **kwargs):
        pass


class LangfuseTracer:
    """Langfuse 追踪器包装"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._client = None
        self._enabled = bool(
            self.settings.langfuse_public_key
            and self.settings.langfuse_secret_key
            and self.settings.langfuse_host
        )
        if self._enabled:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=self.settings.langfuse_public_key,
                    secret_key=self.settings.langfuse_secret_key,
                    host=self.settings.langfuse_host,
                )
            except Exception as e:
                logger.warning(f"Langfuse 初始化失败: {e}")
                self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    @contextmanager
    def trace(
        self,
        name: str,
        evaluation_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self._enabled or not self._client:
            yield NoOpTrace()
            return

        trace = self._client.trace(
            name=name,
            id=evaluation_id,
            user_id=employee_id,
            metadata=metadata or {},
        )
        try:
            yield trace
        finally:
            # Langfuse 客户端自动刷新，无需显式操作
            pass

    @contextmanager
    def span(self, parent, name: str, input_data: Optional[Any] = None):
        if not self._enabled or not self._client or parent is None:
            yield NoOpTrace()
            return

        span = parent.span(
            name=name,
            input=input_data,
        )
        try:
            yield span
        finally:
            pass

    def generation(
        self,
        parent,
        name: str,
        prompt: Optional[str] = None,
        completion: Optional[str] = None,
        model: Optional[str] = None,
        usage: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """记录模型生成调用"""
        if not self._enabled or not self._client or parent is None:
            return NoOpTrace()

        gen = parent.generation(
            name=name,
            input=prompt,
            output=completion,
            model=model,
            usage=usage,
            metadata=metadata or {},
        )
        return gen

    def close(self) -> None:
        """刷新并关闭 Langfuse 客户端"""
        if self._enabled and self._client:
            try:
                self._client.flush()
                self._client.shutdown()
            except Exception as e:
                logger.warning(f"Langfuse 客户端关闭失败: {e}")
        self._enabled = False
        self._client = None


# 全局单例
tracer = LangfuseTracer()
