# -*- coding: utf-8 -*-
"""大模型客户端封装（Anthropic 协议版）。

为什么是 Anthropic 协议：用户的智谱额度在
https://open.bigmodel.cn/api/anthropic（编程套餐端点），
而 /api/paas/v4 走的是独立的 API 按量计费池（为空，报 1113）。
换端点 = 换协议 = 换 SDK，这就是"协议方言"的实战含义。
"""
import asyncio
import json
import logging
import time
from typing import AsyncIterator, List, Optional, Tuple

from anthropic import AsyncAnthropic, RateLimitError
from fastapi import HTTPException
from app.config import get_settings
from app.schemas import ChatRequest

logger = logging.getLogger("llm-api")


def _upstream_guard(exc: Exception) -> HTTPException:
    """把上游模型的故障翻译成对客户端友好的 503，而不是裸 500。"""
    logger.error("上游模型调用失败：%s", exc)
    return HTTPException(status_code=503, detail="上游模型服务繁忙或额度不足，请稍后再试")


def _split_system(req: ChatRequest) -> Tuple[Optional[str], List[dict]]:
    """Anthropic 协议要求 system 独立于 messages 之外。"""
    system = "\n".join(m.content for m in req.messages if m.role == "system")
    msgs = [{"role": m.role, "content": m.content}
            for m in req.messages if m.role in ("user", "assistant")]
    return (system or None), msgs


def get_client() -> AsyncAnthropic:
    settings = get_settings()
    return AsyncAnthropic(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.request_timeout,
    )


async def complete(req: ChatRequest) -> str:
    """非流式补全。"""
    settings = get_settings()
    client = get_client()
    system, msgs = _split_system(req)
    try:
        resp = await client.messages.create(
            model=req.model or settings.llm_model,
            system=system,
            messages=msgs,
            max_tokens=settings.max_tokens,
            temperature=req.temperature,
        )
    except RateLimitError as exc:
        raise _upstream_guard(exc) from exc
    return "".join(b.text for b in resp.content if b.type == "text")


async def stream_complete(req: ChatRequest) -> AsyncIterator[str]:
    """流式补全（SSE）：上游每吐一段就转发一段；客户端断开时记录并释放。"""
    settings = get_settings()
    client = get_client()
    system, msgs = _split_system(req)
    start = time.perf_counter()
    pieces = 0
    try:
        async with client.messages.stream(
            model=req.model or settings.llm_model,
            system=system,
            messages=msgs,
            max_tokens=settings.max_tokens,
            temperature=req.temperature,
        ) as stream:
            async for text in stream.text_stream:
                if not text:
                    continue
                pieces += 1
                yield "data: %s\n\n" % json.dumps({"content": text}, ensure_ascii=False)
        yield "data: [DONE]\n\n"
        logger.info("流式正常结束：%d 个片段，耗时 %.2fs", pieces, time.perf_counter() - start)
    except RateLimitError as exc:
        raise _upstream_guard(exc) from exc
    except asyncio.CancelledError:
        logger.warning("客户端中途断开，流式中止（已发 %d 个片段，%.2fs），上游已停止消费",
                       pieces, time.perf_counter() - start)
        raise
