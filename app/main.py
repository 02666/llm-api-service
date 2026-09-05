# -*- coding: utf-8 -*-
"""FastAPI 入口：装配中间件、路由；本文件不知道任何业务细节"""
import logging
import time

from fastapi import FastAPI, Request

from app.routers import chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("llm-api")

app = FastAPI(
    title="LLM Chat API",
    version="0.1.0",
    description="生产级 LLM Chat API 学习项目：鉴权 / 限流 / 流式 / 可观测",
)


@app.middleware("http")
async def add_timing(request: Request, call_next):
    """计时中间件：每个请求的耗时都记录在响应头和日志里（可观测的最小形态）。"""
    start = time.perf_counter()
    response = await call_next(request)
    cost = time.perf_counter() - start
    response.headers["X-Process-Time"] = "%.4f" % cost
    logger.info("%s %s -> %s (%.3fs)", request.method, request.url.path,
                response.status_code, cost)
    return response


app.include_router(chat.router)


@app.get("/healthz", tags=["ops"])
async def healthz():
    """健康检查：负载均衡 / 容器探针用。"""
    return {"status": "ok"}
