# -*- coding: utf-8 -*-
"""/v1/chat/* 路由：只做编排（验货后的请求 → 调 LLM → 组响应），不含业务细节"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.dependencies import verify_api_key
from app.llm import complete, stream_complete
from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/v1/chat", tags=["chat"])


@router.post("/completions", response_model=ChatResponse)
async def chat_completions(req: ChatRequest, key: str = Depends(verify_api_key)):
    settings = get_settings()
    content = await complete(req)
    return ChatResponse(model=req.model or settings.llm_model, content=content)


@router.post("/stream")
async def chat_stream(req: ChatRequest, key: str = Depends(verify_api_key)) -> StreamingResponse:
    """SSE 流式接口：逐字转发模型输出。

    注意：鉴权（Depends）发生在流开始之前 —— 无 Key 的请求拿 401 走人，
    一个 token 都不会烧。
    """
    return StreamingResponse(
        stream_complete(req),
        media_type="text/event-stream",          # SSE 协议的固定 Content-Type
        headers={
            "Cache-Control": "no-cache",         # 禁止任何缓存，保证是"实时"流
            "X-Accel-Buffering": "no",           # 告诉 Nginx 别攒齐再发（W4 部署时生效）
        },
    )
