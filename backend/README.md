# 快递企业智能客服 · 后端

FastAPI + LangGraph 后端，uv 管理，本机裸跑（无需 Docker）。

## 快速开始

```bash
cd backend
uv sync                          # 读取 pyproject.toml 安装依赖
uv run python -m uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000/docs 查看接口文档
# GET /health           存活探针
# GET /api/v1/health    就绪探针（校验数据库连通）
```

## 目录结构

```
backend/
├── pyproject.toml          # uv 依赖与工具配置
├── .env.example            # 环境变量示例（复制为 .env）
└── app/
    ├── main.py             # FastAPI 入口 + CORS + /health
    ├── core/               # 配置(config)、日志、安全、依赖注入
    ├── api/                # REST/WS 路由 + 依赖注入(deps)
    ├── db/                 # SQLAlchemy 引擎/会话/ORM 基类
    ├── models/             # Pydantic 模型（请求/响应 schema）
    ├── agent/              # LangGraph 编排（state/nodes/graph/router）
    ├── capabilities/       # workflow / rag / graphrag
    ├── retrieval/          # 混合检索 + rerank（hybrid）
    └── platform/           # 多租户 / RBAC / 监控 / 审计
```

## Agent Harness：工具、循环、上下文与 Prompt

`app/agent` 同时包含一套小而完整的供应商无关 Harness：

| 模块 | 职责 | 关键保护 |
|---|---|---|
| `tools.py` | 工具注册、schema 导出和执行 | 白名单、必填/类型/额外参数校验、异常封装 |
| `loop.py` | Observe/Decide/Act/Guard/Answer | `max_steps`、重复调用终止、trace |
| `context.py` | 上下文装配 | 来源优先级、总预算、单条截断、dropped 记录 |
| `prompting.py` | Prompt 结构与版本 | 角色/目标/策略/安全/完成标准分层、边界转义、`agent-loop-v2` 版本 |
| `planner.py` | 真实模型 structured tool calling 适配 | 只产生决策，不直接执行代码 |
| `business_tools.py` | BusinessGateway 工具化 | 只暴露无副作用查询 |
| `service.py` | `execute` 节点内的只读工具能力 | 场景门控、grounding guard |

Planner 只需实现一个方法，因此可以在不改 Loop 的情况下切换 DeepSeek、OpenAI 兼容模型或测试用脚本 Planner：

```python
class Planner:
    def decide(self, prompt: str, tools: list[dict]) -> AgentDecision:
        ...  # 返回 kind="tool" 或 kind="final"
```

运行不依赖远程模型的完整示例：

```bash
uv run python -m examples.agent_loop_demo
```

示例会注册 `query_logistics` 工具，执行一次决策循环，输出最终回复与可审计 trace。接入真实模型时，应将模型的 structured tool call 转为 `AgentDecision`；不要让模型直接执行 Python 或 Shell。

上下文推荐优先级：安全/租户规则 > 已核验业务结果 > 最近对话 > 检索候选。工具输出始终当作不可信数据，不应被提升为系统指令。

### 统一主链路中的 Tool-calling

前端始终调用受 `chat:write` RBAC 保护的原有接口：

```http
POST /api/v1/chat
Authorization: Bearer <JWT>
Content-Type: application/json

{"message":"查一下 SF12345678 的物流","session_id":"demo-1"}
```

该请求经 LangGraph `understand -> execute -> respond` 主链路，在 `execute` 中将“已有完整单号的物流查询”交给 AgentLoop。缺少单号时由 Workflow 追问，非物流问题不会进入该 Loop。无 API Key 时会回退到原有确定性 Workflow。

### Agent 评测

`GET /api/v1/evals/agent` 返回以下可机读指标：

- `task_success_rate`：给定脚本决策后，Harness 终止状态是否符合预期；
- `tool_dispatch_conformance`：Harness 是否按给定决策派发工具；
- `argument_dispatch_conformance`：Harness 是否按给定决策传递参数；
- `unsafe_action_rate`：未授权工具是否被真正执行，目标为 0。

当前回归集覆盖正确物流查询、参数缺失、未授权 Shell 调用和未经工具核验的直接回答。
这些数字是确定性 Harness 回归，**不是真实 LLM 的工具选择准确率**。

### Badcase 回归集

`data/evals/badcases.jsonl` 是可版本控制的脱敏 badcase 数据集。每行保存输入、预期路由、
模型档位、风险等级、类别和“要防止的回归”。当前覆盖咨询误触发、越权提示注入、缺单号物流、
复杂关联推理和不可信工具指令。`GET /api/v1/evals/badcases` 可供管理员查看案例；
`GET /api/v1/evals/report` 会单独返回 `badcase.passRate`、失败数和失败案例 ID。

新增线上问题时，先脱敏，再追加一行 JSONL，并运行：

```bash
uv run pytest tests/test_evals.py -q --basetemp .pytest-tmp
```

## 配置分层

配置集中在 `app/core/config.py`，按层级拆分（app/database/redis/neo4j/chroma/embedding/llm），
通过 `.env` 覆盖默认值（字段命名 `<层级>__<字段>`，双下划线）。中间件默认指向本机：

| 中间件 | 默认地址 | 说明 |
|---|---|---|
| 数据库 | SQLite | 阶段 9 换 MySQL |
| Redis | redis://localhost:6379/0 | checkpoint，开发期可用 MemorySaver |
| Neo4j | bolt://localhost:7687 | 图谱 |
| Chroma | 进程内 | 持久化到 ./data/chroma |
| 向量模型 | 本地 ../models | bge-base-zh-v1.5 缓存 |

生产环启动时会 fail fast：禁止默认/短 JWT 密钥、MemorySaver 和进程内限流。生产 `.env` 至少需要：

```dotenv
APP__ENVIRONMENT=production
PLATFORM__JWT_SECRET=<至少 32 位随机密钥>
PLATFORM__RATE_LIMIT_BACKEND=redis
AGENT__CHECKPOINT_BACKEND=redis
REDIS__URL=redis://redis:6379/0
```

Compose 使用 `redis/redis-stack-server`，因为 RedisSaver 依赖 RedisJSON 和 RediSearch；普通 `redis:7` 不能作为完整替代。

## 常用命令

```bash
uv run pytest          # 测试
uv run pytest tests/test_agent_loop.py -q  # Agent Harness 定向测试
uv run ruff check .    # 静态检查
```

## Agent 评测与压测

管理员可调用 `POST /api/v1/evals/run`（或 `GET /api/v1/evals/report`）获取可机读的
路由与安全回归报告。评测集覆盖闲聊、工作流、知识库、GraphRAG、咨询不误触发业务和
可疑提示词；它不调用远程模型，因此适合每次提交和 CI 运行。

真实 SSE 接口的并发压测会记录成功率、首字延迟和总延迟的 P50/P95/P99，并可保存 JSON
报告。令牌仅从命令行读取，不会写入报告：

```powershell
$env:STACKLANG_TOKEN = "<你的 JWT>"
uv run python scripts/load_test.py --token $env:STACKLANG_TOKEN --requests 20 --concurrency 5 --report reports/load.json
```

## 真实 GraphRAG 验证

`tests/test_graphrag.py` 使用 FakeDriver，用于验证编排、自校正和用户过滤逻辑，**不代表真实 Neo4j 已连通**。面试或发布前应启动 Neo4j、配置 LLM Key，然后运行：

```powershell
$env:RUN_NEO4J_INTEGRATION = "1"
uv run pytest tests/test_graphrag_integration.py -q -s
# 或直接查看问题、生成的 Cypher 和记录
uv run python -m scripts.verify_graphrag
```

验证脚本会写入一组带 `verification_fixture=true` 的隔离数据，向真实 LLM 提问“白色 256G 手机有哪些”，经 `EXPLAIN`、Text2Cypher 和 Neo4j 实际执行后断言命中预期 SKU，最后只清理该隔离数据。

## 真实 Redis 验证

```powershell
$env:RUN_REDIS_INTEGRATION = "1"
uv run pytest tests/test_redis_integration.py -q -s
# 或查看验证报告
uv run python -m scripts.verify_redis
```

该验证会用两个独立 `RedisRateLimiter` 实例证明窗口计数共享，并用两个独立 `RedisSaver`/Graph 实例证明 checkpoint 可跨实例恢复。应用 lifespan 在启动时执行 `setup()`，在停止时关闭 RedisSaver 和限流客户端。

## 前端 Token 策略

前端不再从 `VITE_DEV_TOKEN` 读取 JWT，也不再默认注入管理员用户。`VITE_*` 会进入浏览器构建物，不应承载凭证。Token 必须由显式登录/SSO 流程通过 `auth.login(token, user)` 写入；未登录请求由后端统一返回 401。

## 业务供应商切换

订单、物流、售后操作通过统一适配层调用。`BUSINESS_INTEGRATION__PROVIDER=local`
使用本地数据库；`demo` 使用明确标注的沙盒供应商；生产环境使用 `http`，并配置
`BUSINESS_INTEGRATION__BASE_URL` 与 `BUSINESS_INTEGRATION__API_TOKEN`。HTTP 模式内置请求超时、
有限重试与熔断保护，网关路径约定为 `/logistics/{tracking_no}`、`/orders/{id}/address` 和
`/after-sales/returns`。

## 常见问题

### Windows 中文路径下 Python 无法启动（GBK 解码错误）

项目路径含中文（如 `录制课程/栈语`）时，可编辑安装会把源码路径写入 `.pth`，
而 Python 3.11 的 `site.py` 以 GBK 读取该文件导致解码失败（`PYTHONUTF8` 不影响此步）。
已在 `pyproject.toml` 用 `[tool.uv] package = false` 规避：不安装为可编辑包，
改用 `python -m uvicorn` 从 `backend/` 目录运行（`app` 包靠 CWD 导入）。
