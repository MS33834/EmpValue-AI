"""
EmpValue-AI 应用配置
优先从环境变量读取，本地开发可使用 .env 文件。
"""

from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EmpValue-AI"
    debug: bool = False

    # 模型档位强制设定，可选 auto / L0 / L1 / L2 / L3
    model_tier: Literal["auto", "L0", "L1", "L2", "L3"] = "auto"

    # 云端 API 配置
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # 本地 LM Studio / Ollama 配置（OpenAI 兼容接口）
    local_base_url: str = "http://localhost:1234/v1"
    local_api_key: Optional[str] = "lm-studio"
    local_model_l1: str = "qwen2.5-0.5b-instruct"
    local_model_l2: str = "qwen2.5-7b-instruct"
    local_model_l3: str = "qwen2.5-14b-instruct"

    # 默认推理参数
    temperature: float = 0.1
    max_tokens: int = 4096

    # Langfuse 可观测性配置
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
