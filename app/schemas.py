# -*- coding: utf-8 -*-
"""数据契约：全项目的 Pydantic 模型都放这（请求进来先在这验货）"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)  # 上限防 token 被刷


class ChatRequest(BaseModel):
    model: Optional[str] = None          # 不传就用服务端默认模型
    messages: List[Message] = Field(min_length=1, max_length=50)
    temperature: float = Field(default=0.7, ge=0, le=2)
    stream: bool = False                 # W2 的 SSE 流式开关


class ChatResponse(BaseModel):
    model: str
    content: str
