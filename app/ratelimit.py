# -*- coding: utf-8 -*-
"""按 API Key 限流（W3）：固定窗口计数（INCR + EXPIRE）。

设计决策：fail-open —— Redis 不可用时放行并告警。
限流器的故障不应该拖垮整个服务：宁可暂时不限流，不能让服务整体不可用。
（反过来 fail-closed 的场景是付费 API 计费，宁可拒服也不能漏计费。）
"""
import logging
import time
from typing import Optional, Tuple

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger("llm-api")

_client: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    """懒加载全局 Redis 连接（首次请求才建立，避免服务启动被 Redis 绑架）。"""
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.redis_url, socket_connect_timeout=1)
    return _client


async def check_rate_limit(key: str) -> Tuple[bool, int]:
    """检查某 API Key 本分钟是否还有配额。

    返回 (是否放行, 建议等待秒数)。
    固定窗口算法：以"分钟编号"为桶，每来一个请求计数 +1，
    首次计数时给计数器设 60 秒过期 —— 过期自动清零，无需后台任务。
    """
    settings = get_settings()
    if settings.rate_limit_per_minute <= 0:
        return True, 0

    client = _get_redis()
    if client is None:
        return True, 0

    bucket = int(time.time() // 60)                 # 当前分钟编号（如 28937642）
    redis_key = "rate:%s:%d" % (key, bucket)
    try:
        count = await client.incr(redis_key)        # 原子自增，并发安全
        if count == 1:
            await client.expire(redis_key, 60)      # 只有第一个请求设置过期
        if count > settings.rate_limit_per_minute:
            retry_after = 60 - int(time.time() % 60) + 1
            logger.info("限流生效：Key=%s 本分钟第 %d 次请求被拒", key, count)
            return False, retry_after
        return True, 0
    except Exception as exc:
        logger.warning("Redis 不可用，限流降级放行：%s", exc)
        return True, 0
