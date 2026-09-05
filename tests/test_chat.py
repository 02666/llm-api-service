# -*- coding: utf-8 -*-
"""核心接口测试：不起服务器，直接打接口（跑法：项目根目录执行 pytest -v）"""
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "dev-key-123"}


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "X-Process-Time" in r.headers   # 计时中间件生效


def test_missing_key_returns_401():
    r = client.post("/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


def test_wrong_key_returns_401():
    r = client.post("/v1/chat/completions", headers={"X-API-Key": "bad-key"},
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


def test_invalid_body_returns_422():
    # messages 为空列表 → 违反 min_length=1 → Pydantic 打回
    r = client.post("/v1/chat/completions", headers=HEADERS, json={"messages": []})
    assert r.status_code == 422


def test_invalid_role_returns_422():
    r = client.post("/v1/chat/completions", headers=HEADERS,
                    json={"messages": [{"role": "hacker", "content": "hi"}]})
    assert r.status_code == 422


def test_chat_with_mocked_llm(monkeypatch):
    """业务链路测试：mock 掉 LLM，只验证 FastAPI 这条链路是对的。"""
    async def fake_complete(req):
        return "MOCK-ANSWER"

    monkeypatch.setattr("app.routers.chat.complete", fake_complete)
    r = client.post("/v1/chat/completions", headers=HEADERS,
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "MOCK-ANSWER"
    assert body["model"]       # 默认模型名回填了


def test_stream_requires_key_401():
    """流式接口同样受鉴权保护：无 Key 401，不会烧任何 token。"""
    r = client.post("/v1/chat/stream",
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


def test_stream_sse_format(monkeypatch):
    """验证 SSE 报文格式：Content-Type、data: 前缀、结束标记。"""
    async def fake_stream(req):
        for piece in ["你", "好"]:      # 模拟模型逐字吐字
            yield "data: %s\n\n" % json.dumps({"content": piece}, ensure_ascii=False)
        yield "data: [DONE]\n\n"

    monkeypatch.setattr("app.routers.chat.stream_complete", fake_stream)
    r = client.post("/v1/chat/stream", headers=HEADERS,
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"content": "你"}' in r.text
    assert 'data: {"content": "好"}' in r.text
    assert r.text.endswith("data: [DONE]\n\n")
