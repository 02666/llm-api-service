# -*- coding: utf-8 -*-
"""配置管理：所有配置集中在这，从环境变量 / .env 读取，代码零硬编码"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 鉴权：逗号分隔的合法 API Key 列表
    api_keys: str = "dev-key-123"

    # 大模型供应商（DeepSeek 示例，换 Qwen/vLLM 只改环境变量）
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # 单次请求超时（秒）
    request_timeout: float = 60.0

    # 限流（W3）：每个 API Key 每分钟最大请求数；<=0 表示不限制
    rate_limit_per_minute: int = 10
    redis_url: str = "redis://localhost:6379/0"

    @property
    def valid_keys(self):
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
