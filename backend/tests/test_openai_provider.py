"""
OpenAI 兼容 Provider 单元测试
验证重试、超时与错误处理逻辑，避免真实网络调用。
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from openai import APIConnectionError, InternalServerError, RateLimitError

from core.providers.base import ChatMessage, ProviderConfig
from core.providers.openai_provider import OpenAICompatibleProvider


def _fake_response(content="hello"):
    """构造一个伪造的 OpenAI 接口返回对象"""
    resp = MagicMock()
    resp.model = "gpt-4o-mini"
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage.prompt_tokens = 1
    resp.usage.completion_tokens = 1
    resp.usage.total_tokens = 2
    return resp


def _make_connection_error():
    request = httpx.Request("POST", "http://localhost/v1/chat/completions")
    return APIConnectionError(message="connection lost", request=request)


def _make_rate_limit_error():
    request = httpx.Request("POST", "http://localhost/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limit exceeded", response=response, body=None)


def _make_internal_error():
    request = httpx.Request("POST", "http://localhost/v1/chat/completions")
    response = httpx.Response(500, request=request)
    return InternalServerError("internal server error", response=response, body=None)


@pytest.mark.asyncio
async def test_chat_completion_retries_then_succeeds(monkeypatch):
    """前两次触发可重试错误，第三次成功，应返回结果并重试 2 次。"""
    mock_create = AsyncMock(
        side_effect=[
            _make_connection_error(),
            _make_rate_limit_error(),
            _fake_response("success"),
        ]
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    provider = OpenAICompatibleProvider(
        ProviderConfig(model_name="gpt-4o-mini", api_key="fake-key")
    )
    provider.client = mock_client
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    result = await provider.chat_completion([ChatMessage(role="user", content="hi")])

    assert result.content == "success"
    assert mock_create.call_count == 3


@pytest.mark.asyncio
async def test_chat_completion_raises_after_retries_exhausted(monkeypatch):
    """连续失败超过最大重试次数后，应抛出清晰的 RuntimeError。"""
    mock_create = AsyncMock(side_effect=_make_internal_error())
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    provider = OpenAICompatibleProvider(
        ProviderConfig(model_name="gpt-4o-mini", api_key="fake-key")
    )
    provider.client = mock_client
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    with pytest.raises(RuntimeError, match="调用失败"):
        await provider.chat_completion([ChatMessage(role="user", content="hi")])

    # 首次 + 3 次重试 = 4 次调用
    assert mock_create.call_count == 4


@pytest.mark.asyncio
async def test_chat_completion_passes_timeout(monkeypatch):
    """调用时应携带超时参数。"""
    mock_create = AsyncMock(return_value=_fake_response("ok"))
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    provider = OpenAICompatibleProvider(
        ProviderConfig(model_name="gpt-4o-mini", api_key="fake-key")
    )
    provider.client = mock_client

    await provider.chat_completion([ChatMessage(role="user", content="hi")])

    _, kwargs = mock_create.call_args
    assert "timeout" in kwargs
    assert kwargs["timeout"] == 30.0
