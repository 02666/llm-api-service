# -*- coding: utf-8 -*-
"""大模型客户端封装：业务代码只认 complete()/stream_complete()，底层换 DeepSeek/Qwen/vLLM 零改动"""
import asyncio
import json
import logging
import time
from typing import AsyncIterator

from fastapi import HTTPException
from openai import AsyncOpenAI, RateLimitError
from app.config import get_settings
from app.schemas import ChatRequest

logger = logging.getLogger("llm-api")


def _upstream_guard(exc: Exception) -> HTTPException:
    """把上游模型的故障翻译成对客户端友好的 503，而不是裸 500。"""
    logger.error("上游模型调用失败：%s", exc)
    return HTTPException(status_code=503, detail="上游模型服务繁忙或额度不足，请稍后再试")


def get_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.request_timeout,   # 超时保命：上游卡死不拖垮服务
    )


async def complete(req: ChatRequest) -> str:
    """非流式补全（W1）。流式版本见 W2 里程碑。"""
    settings = get_settings()
    client = get_client()
    try:
        resp = await client.chat.completions.create(
            model=req.model or settings.llm_model,
            messages=[m.model_dump() for m in req.messages],
            temperature=req.temperature,
        )
    except RateLimitError as exc:
        raise _upstream_guard(exc) from exc
    return resp.choices[0].message.content or ""


async def stream_complete(req: ChatRequest) -> AsyncIterator[str]:
    """流式补全（W2）：每次 yield 一行已编码的 SSE 数据（data: {...}\\n\\n）。

    W2.1 修正：处理客户端中途断开 —— 否则取消是静默的，
    上游模型还在生成、还在计费，服务端却毫无感知。
    """
    settings = get_settings()
    client = get_client()
    # stream=True：SDK 返回一个异步迭代器，模型每生成一小段就推送一个 chunk
    try:
        stream = await client.chat.completions.create(
            model=req.model or settings.llm_model,
            messages=[m.model_dump() for m in req.messages],
            temperature=req.temperature,
            stream=True,
        )
    except RateLimitError as exc:
        raise _upstream_guard(exc) from exc
    start = time.perf_counter()
    pieces = 0
    try:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content   # delta = 增量片段（不是全文！）
            if not delta:
                continue                             # 开头的 role 块等无内容片段，跳过
            pieces += 1
            yield "data: %s\n\n" % json.dumps({"content": delta}, ensure_ascii=False)
        yield "data: [DONE]\n\n"                     # OpenAI 风格的结束标记
        logger.info("流式正常结束：%d 个片段，耗时 %.2fs", pieces, time.perf_counter() - start)
    except asyncio.CancelledError:
        # 客户端断开 → Uvicorn 取消本任务 → 在 await/yield 处抛到这里。
        # 必须记日志 + 重新抛出：吞掉它会破坏 asyncio 的取消协议。
        logger.warning("客户端中途断开，流式中止（已发 %d 个片段，%.2fs），上游已停止消费",
                       pieces, time.perf_counter() - start)
        raise
    finally:
        # 无论正常结束还是被取消，都关闭上游连接，释放资源
        close = getattr(stream, "close", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result
