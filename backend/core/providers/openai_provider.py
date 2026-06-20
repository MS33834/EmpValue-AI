"""
OpenAI 兼容 Provider
同时支持：OpenAI 官方、Azure、LM Studio、Ollama、DeepSeek、阿里云百炼等。
"""

from typing import Dict, List, Optional

from openai import AsyncOpenAI

from .base import BaseProvider, ChatCompletion, ChatMessage, ProviderConfig


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI 兼容 API Provider"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        kwargs: Dict[str, str] = {}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        if config.api_key:
            kwargs["api_key"] = config.api_key
        self.client = AsyncOpenAI(**kwargs)

    def name(self) -> str:
        return f"openai-compatible/{self.config.model_name}"

    async def chat_completion(
        self,
        messages: List[ChatMessage],
        response_format: Optional[Dict[str, str]] = None,
    ) -> ChatCompletion:
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = await self.client.chat.completions.create(**payload)
        content = resp.choices[0].message.content or ""
        # 清理可能的 Markdown 代码块
        content = self._strip_markdown_json(content)
        return ChatCompletion(
            content=content,
            model=resp.model or self.config.model_name,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                "total_tokens": resp.usage.total_tokens if resp.usage else 0,
            },
        )

    async def health_check(self) -> bool:
        try:
            # LM Studio / Ollama 可用模型列表接口与 OpenAI 兼容
            models = await self.client.models.list()
            model_ids = [m.id for m in models.data]
            return self.config.model_name in model_ids or len(model_ids) > 0
        except Exception:
            return False

    @staticmethod
    def _strip_markdown_json(content: str) -> str:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()
