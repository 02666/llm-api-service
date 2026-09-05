# -*- coding: utf-8 -*-
"""依赖注入：鉴权等"某些接口才需要"的公共动作，声明一次处处复用"""
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: Optional[str] = Security(api_key_header)) -> str:
    """校验 X-API-Key 请求头；不合法直接 401，处理函数不会执行。"""
    settings = get_settings()
    if not key or key not in settings.valid_keys:
        raise HTTPException(status_code=401, detail="无效或缺失的 API Key")
    return key
