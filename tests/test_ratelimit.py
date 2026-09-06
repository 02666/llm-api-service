# -*- coding: utf-8 -*-
"""限流算法测试：用 fakeredis（内存版 Redis，接口与真实 Redis 一致）验证真实计数逻辑。
不需要启动任何服务器，也不依赖 Docker。

注意：FakeRedis 必须在事件循环内部创建（绑定循环），所以统一通过 _run() 执行。"""
import asyncio

import fakeredis.aioredis

from app import ratelimit


def _run(monkeypatch, limit: int, coro_fn):
    """在同一个事件循环里：创建 FakeRedis → 注入 → 设阈值 → 执行测试逻辑。"""
    async def main():
        fake = fakeredis.aioredis.FakeRedis()
        monkeypatch.setattr(ratelimit, "_client", fake)
        settings = ratelimit.get_settings()
        monkeypatch.setattr(settings, "rate_limit_per_minute", limit)
        return await coro_fn()
    return asyncio.run(main())


def test_fixed_window_allows_then_rejects(monkeypatch):
    """限流=2 的设定下：第 1、2 次放行，第 3 次拒绝，并给出等待秒数。"""
    async def coro_fn():
        return [await ratelimit.check_rate_limit("user-A") for _ in range(3)]

    results = _run(monkeypatch, limit=2, coro_fn=coro_fn)
    assert results[0] == (True, 0)
    assert results[1] == (True, 0)
    assert results[2][0] is False
    assert 1 <= results[2][1] <= 60        # 告诉客户端等到本窗口结束


def test_different_keys_have_separate_quotas(monkeypatch):
    """不同 API Key 配额互不影响：A 用光了不影响 B。"""
    async def coro_fn():
        a1 = await ratelimit.check_rate_limit("user-A")
        b1 = await ratelimit.check_rate_limit("user-B")
        a2 = await ratelimit.check_rate_limit("user-A")
        return a1, b1, a2

    a1, b1, a2 = _run(monkeypatch, limit=1, coro_fn=coro_fn)
    assert a1 == (True, 0)
    assert b1 == (True, 0)
    assert a2[0] is False                  # A 的第二次：本窗口配额已用尽


def test_disabled_limit_allows_everything(monkeypatch):
    """阈值设为 0 = 关闭限流：怎么打都放行，甚至不碰 Redis。"""
    async def coro_fn():
        return [await ratelimit.check_rate_limit("user-A") for _ in range(5)]

    results = _run(monkeypatch, limit=0, coro_fn=coro_fn)
    assert all(r == (True, 0) for r in results)
