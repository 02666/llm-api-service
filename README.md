# LLM Chat API

生产级 LLM Chat API —— 把 Agent/RAG 能力"服务化"的骨架工程。
**FastAPI + Anthropic 协议 + SSE 流式 + Redis 限流 + pytest**，单机实测最高 1266 RPS（5 并发 P99 仅 9.7ms），27 万压测请求零失败。

## 功能特性

- **双协议模型接入**：Anthropic 协议（智谱编程套餐端点）实时验证通过；`llm.py` 客户端封装隔离供应商，换 DeepSeek/Qwen/vLLM 只改 `.env`
- **SSE 流式输出**：逐字转发，客户端断开时捕获 `CancelledError` 记录日志并释放上游连接
- **API Key 鉴权**：`Depends` 依赖注入，未授权请求 401 且不占配额
- **按 Key 限流**：Redis 固定窗口（INCR 原子计数 + EXPIRE 自动重置），超限返回 429 + Retry-After；**Redis 故障 fail-open 降级**，服务可用性优先
- **上游故障转译**：上游 429/欠费/异常 → 友好 503，不裸奔堆栈
- **可观测**：请求耗时中间件（X-Process-Time）、流式真实时长与片段数日志
- **自动化测试**：13 项 pytest 用例（鉴权/校验/业务链路/流式格式/限流算法/fail-open），fakeredis 验证计数逻辑无需真实服务器

## 快速开始

```bash
pip install -r requirements.txt          # 需要 Python 3.9+
cp .env.example .env                     # 填入你的 LLM_API_KEY
docker compose up -d redis               # 启动 Redis（限流依赖）
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 打开 http://127.0.0.1:8000/docs 交互试用；或：
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream -H "X-API-Key: dev-key-123" ^
     -H "Content-Type: application/json" -d "{\"messages\": [{\"role\": \"user\", \"content\": \"你好\"}]}"
```

## 测试

```bash
pytest -v          # 13 passed：健康检查 / 401×2 / 422×2 / 业务链路(mock) / 流式 / 限流
pytest --cov=app --cov-report=term
```

## 压测结果

自研压测器（`sweep.py` 驱动 `loadgen.py`，httpx+asyncio），端点 `/v1/chat/completions`，mock LLM 场景（度量框架自身开销），限流关闭，单 worker，每轮 60s（预热 5s 丢弃）。同一时段连续测量 6 个梯度：

| 并发 | 总请求 | 失败 | RPS | P50 | P95 | P99 | 最大 |
|---|---|---|---|---|---|---|---|
| 5  | 75,939 | 0 | **1265.7** | 3.5ms | 5.6ms | **9.7ms** | 159.9ms |
| 10 | 47,054 | 0 | 784.2 | 6.3ms | 37.7ms | 169.6ms | 695.9ms |
| 20 | 35,725 | 0 | 595.4 | 15.0ms | 121.2ms | 215.6ms | 576.5ms |
| 30 | 29,471 | 0 | 491.2 | 30.4ms | 207.1ms | 376.0ms | 917.5ms |
| 40 | 19,262 | 0 | 321.0 | 69.3ms | 412.7ms | 837.5ms | 3157.9ms |
| 50 | 17,674 | 0 | 294.6 | 100.6ms | 555.2ms | 1087.5ms | 3014.5ms |

**曲线结论**：单 worker 下吞吐从 5 并发起即随并发单调下降（1266 → 295 RPS），P99 同步恶化（9.7ms → 1087ms）。拐点在 10~20 并发之间：P95 从 37.7ms 跳到 121.2ms，吞吐开始明显下滑。**当前架构的最大产能 ≈ 1266 RPS（5 并发即达到）**，更多并发只会增加排队——扩容靠多 worker / 多实例，而不是堆并发。全部 27 万请求零失败。

复现：`python sweep.py`（⚠️ 压测器已内置 `trust_env=False` 直连，否则系统代理会注入 502 污染数据——实测踩坑；同机压测存在 ±20% 运行间波动）。

## 架构

请求链路：`客户端 → Nginx(生产) → Uvicorn → 中间件 → 路由 → 鉴权(Depends) → 限流(Redis) → Pydantic 校验 → 业务函数 → 上游模型`

```
llm-api-service/
├── app/
│   ├── main.py          # 入口 + 计时/日志中间件
│   ├── config.py        # pydantic-settings（.env 驱动）
│   ├── dependencies.py  # 鉴权 + 限流组合依赖
│   ├── ratelimit.py     # 固定窗口限流器（fail-open）
│   ├── schemas.py       # Pydantic 数据契约
│   ├── llm.py           # Anthropic 协议客户端（流式/非流式/mock）
│   └── routers/chat.py  # /v1/chat/* 路由
├── tests/               # test_chat.py + test_ratelimit.py（fakeredis）
├── loadgen.py           # 自研压测器
├── sweep.py             # 并发梯度扫测脚本（调 loadgen）
└── experiments/         # 排障/验证实验脚本归档
├── loadgen.py           # 自研压测器
├── Dockerfile / docker-compose.yml（api + redis）
└── README.md
```

## 里程碑

- [x] W1：路由 + Pydantic 校验 + 配置管理 + /docs + 鉴权
- [x] W2：SSE 流式 + 客户端断开处理（CancelledError 捕获/记日志/重抛）
- [x] W3：Redis 按 Key 限流 + fail-open 降级
- [x] W4：压测 + Docker 化 + Anthropic 协议接入 + v1.0.0

## 设计笔记（踩坑实录）

1. **双配额池**：同一把智谱 key，编程套餐端点（/api/anthropic）与 API 按量端点（/api/paas/v4）额度互不相通——1113"余额不足"排查半天，最后发现要换协议而不是换模型。换端点 = 换协议 = 换 SDK。
2. **固定窗口的边界缺陷**：10 个请求跨两个分钟桶（4+6），没有任何桶超限——窗口交界处理论上可放过 2 倍流量。生产应使用滑动窗口/令牌桶。
3. **流式计时盲区**：中间件对 StreamingResponse 只计到"响应头发出"，真实流时长须在生成器内部统计。
4. **压测代理污染**：本机代理会让 httpx 连 localhost 都走代理，注入 502——压测客户端必须 `trust_env=False`。
5. **fail-open vs fail-closed**：限流器故障时放行（可用性优先）；计费场景应反过来。

## 设计动机

LLM 服务与传统 API 的本质区别：**每次调用烧真金白银、响应时长以秒计且不稳定**。
所以鉴权、限流、配额、超时、可观测不是锦上添花，是上线第一天的生死线。
