# -*- coding: utf-8 -*-
"""自研异步压测器：httpx + asyncio。
用法: python loadgen.py [并发数] [持续秒数]
设计：预热阶段样本丢弃；统计 P50/P95/P99 与 RPS；打印失败数。"""
import asyncio
import sys
import time

import httpx

HOST = "http://127.0.0.1:8000"
HEADERS = {"X-API-Key": "dev-key-123", "Content-Type": "application/json"}
PAYLOAD = {"messages": [{"role": "user", "content": "hi"}]}

USERS = int(sys.argv[1]) if len(sys.argv) > 1 else 50
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 60
WARMUP = 5  # 前 5 秒样本丢弃（连接建立期）

latencies = []          # 成功请求耗时（秒）
failures = []


async def worker(client: httpx.AsyncClient, stop_at: float):
    while time.perf_counter() < stop_at:
        t0 = time.perf_counter()
        try:
            r = await client.post("/v1/chat/completions",
                                  headers=HEADERS, json=PAYLOAD)
            cost = time.perf_counter() - t0
            now = time.perf_counter()
            if r.status_code == 200 and now > stop_at - DURATION:
                latencies.append(cost)
            elif r.status_code != 200:
                failures.append((r.status_code, r.text[:80]))
        except Exception as exc:
            failures.append(("EXC", str(exc)[:80]))


async def main():
    async with httpx.AsyncClient(base_url=HOST, timeout=10, trust_env=False,
                                 limits=httpx.Limits(max_connections=200)) as client:
        stop_at = time.perf_counter() + DURATION + WARMUP
        print("压测开始：并发=%d，时长=%ds（预热 %ds 不计入），端点=/v1/chat/completions（mock LLM）"
              % (USERS, DURATION, WARMUP))
        await asyncio.gather(*[asyncio.create_task(worker(client, stop_at)) for _ in range(USERS)])

    latencies.sort()
    n = len(latencies)

    def pct(p):
        if not n:
            return 0
        return latencies[min(n - 1, int(n * p / 100))] * 1000

    total = n + len(failures)
    span = DURATION
    print("-" * 52)
    print("总请求: %d | 成功: %d | 失败: %d" % (total, n, len(failures)))
    if failures:
        print("失败样例:", failures[:3])
    print("吞吐 RPS        : %.1f" % (n / span))
    if n:
        print("延迟 P50        : %.1f ms" % pct(50))
        print("延迟 P95        : %.1f ms" % pct(95))
        print("延迟 P99        : %.1f ms" % pct(99))
        print("延迟 最大        : %.1f ms" % (latencies[-1] * 1000))

asyncio.run(main())
