"""
EmpValue-AI 应用配置
优先从环境变量读取，本地开发可使用 .env 文件。
"""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import model_validator
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

    # 数据库：默认 SQLite（异步），生产可改为 postgresql+asyncpg://...
    database_url: str = "sqlite+aiosqlite:///./empvalue_ai.db"

    # 模型档位强制设定，可选 auto / L0 / L1 / L2 / L3
    model_tier: Literal["auto", "L0", "L1", "L2", "L3"] = "auto"

    # 通用云端 API 配置（OpenAI 兼容，可用于 DeepSeek / 阿里云百炼 / 硅基流动等）
    cloud_api_key: Optional[str] = None
    cloud_base_url: str = "https://api.openai.com/v1"
    cloud_model: str = "gpt-4o-mini"

    # 兼容旧版 OpenAI 命名（未设置 cloud_* 时兜底使用）
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # 本地 LM Studio / Ollama 配置（OpenAI 兼容接口）
    local_base_url: str = "http://localhost:1234/v1"
    local_api_key: Optional[str] = None
    local_model_l1: str = "qwen2.5-0.5b-instruct"
    local_model_l2: str = "qwen2.5-7b-instruct"
    local_model_l3: str = "qwen2.5-14b-instruct"

    # Embedding 配置（OpenAI 兼容接口）
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # 向量库配置
    vector_store_dir: str = "./chroma_db"

    # 附件存储目录（路径遍历防护白名单根目录）
    attachment_dir: str = "./attachments"

    # 默认推理参数
    temperature: float = 0.1
    max_tokens: int = 4096

    # Langfuse 可观测性配置
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # JWT 认证配置：生产环境必须通过环境变量设置强随机密钥
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 小时
    # 演示模式：开启时允许通过 x-user-role / x-user-id header 伪造身份（仅开发/测试用）
    auth_demo_mode: bool = False

    # 运行环境标识：仅当值为 "production" 时启用生产安全校验；
    # 不设或非 production 时不做任何校验，确保开发与测试环境不受影响。
    empvalue_env: Optional[str] = None

    @model_validator(mode="after")
    def _enforce_prod_demo_mode_guard(self) -> "Settings":
        """
        生产环境守护：当处于生产环境（EMPVALUE_ENV=production）且开启演示模式时，
        直接禁止实例化，避免身份伪造能力泄漏到生产。

        安全设计要点：
        - 仅当 empvalue_env == "production" 时才校验，其余情况（含默认 None）完全放行；
        - 现有测试套件不设置 EMPVALUE_ENV，且 conftest 通过 monkeypatch 在已实例化
          对象上修改 auth_demo_mode（model_config 未开启 validate_assignment），
          不会再次触发本校验器，故对现有 486 个测试零影响。
        """
        if self.empvalue_env == "production" and self.auth_demo_mode:
            raise ValueError(
                "生产环境禁止开启 AUTH_DEMO_MODE(auth_demo_mode)"
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()
