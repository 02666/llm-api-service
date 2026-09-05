# LLM Chat API

生产级 LLM Chat API 学习项目 —— 把 Agent/RAG 能力"服务化"的骨架工程。

## 快速开始

```bash
# 1. 安装依赖（推荐虚拟环境）
pip install -r requirements.txt

# 2. 配置
cp .env.example .env      # 填入你的 LLM_API_KEY

# 3. 起服务
uvicorn app.main:app --reload

# 4. 试一把
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/docs        # 自动生成的交互文档
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "X-API-Key: dev-key-123" -H "Content-Type: application/json" \
  -d "{\"messages\": [{\"role\": \"user\", \"content\": \"你好\"}]}"
```

## 测试

```bash
pytest -v          # 6 个用例：健康检查 / 401 / 422 / 业务链路(mock LLM)
```

## 架构

请求链路：`客户端 → Nginx(生产) → Uvicorn → 中间件 → 路由 → 鉴权(Depends) → Pydantic 校验 → 业务函数 → LLM`

```
llm-api-service/
├── app/
│   ├── main.py          # FastAPI 入口 + 计时/日志中间件
│   ├── config.py        # pydantic-settings 配置（.env 驱动）
│   ├── dependencies.py  # X-API-Key 鉴权 Depends
│   ├── schemas.py       # ChatRequest / ChatResponse（数据契约）
│   ├── llm.py           # AsyncOpenAI 客户端封装（可切 vLLM）
│   └── routers/chat.py  # /v1/chat/* 路由
├── tests/test_chat.py
├── Dockerfile / docker-compose.yml（api + redis）
└── README.md
```

## 里程碑

- [x] W1：路由 + Pydantic 校验 + 配置管理 + /docs + 鉴权 + 测试
- [ ] W2：SSE 流式（/v1/chat/stream）+ AsyncOpenAI stream
- [ ] W3：Redis 限流 + 结构化日志升级 + 覆盖率提升
- [ ] W4：压测（locust）+ 压测数据回填 + Docker 部署验证

## 设计动机

LLM 服务与传统 API 的本质区别：**每次调用烧真金白银、响应时长以十秒计且不稳定**。
所以鉴权、限流、配额、超时、可观测不是锦上添花，是上线第一天的生死线。
