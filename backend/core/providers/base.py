"""
Provider 抽象基类
所有 LLM 调用方必须实现此接口，便于云端/本地/其他模型统一接入。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class ProviderConfig:
    """Provider 配置"""

    model_name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    extra: Optional[Dict[str, Any]] = None


@dataclass
class ChatMessage:
    """统一消息格式"""

    role: str
    content: str


@dataclass
class ChatCompletion:
    """统一补全结果"""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None


class BaseProvider(ABC):
    """LLM Provider 抽象基类"""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        response_format: Optional[Dict[str, str]] = None,
    ) -> ChatCompletion:
        """非流式聊天补全"""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """检查该 Provider 是否可用"""
        raise NotImplementedError

    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        raise NotImplementedError
