# -*- coding: utf-8 -*-
"""依赖注入：鉴权、限流等"某些接口才需要"的公共动作，声明一次处处复用"""
from typing import Optional
from fastapi import Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from app.config import get_settings
from app.ratelimit import check_rate_limit

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: Optional[str] = Security(api_key_header)) -> str:
    """校验 X-API-Key 请求头；不合法直接 401，处理函数不会执行。"""
    settings = get_settings()
    if not key or key not in settings.valid_keys:
        raise HTTPException(status_code=401, detail="无效或缺失的 API Key")
    return key


async def verify_key_and_rate_limit(key: str = Depends(verify_api_key)) -> str:
    """组合依赖：先鉴权（401），再对该 Key 限流（429 + Retry-After）。

    依赖可以依赖另一个依赖 —— 链条：rate_limit -> verify_api_key，
    所以未通过鉴权的请求永远走不到限流这一步，也不会占用配额。
    """
    allowed, retry_after = await check_rate_limit(key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after)},   # 告诉客户端几秒后再来
        )
    return key
