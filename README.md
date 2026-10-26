# 快递企业智能客服

面向快递企业的智能客服系统。

- **后端**：Python 3.11 + FastAPI + LangGraph，uv 管理
- **前端**：Vite + Vue 3 + Element Plus + Pinia + Vue Router + Axios
- **中间件**：本机裸跑

## 目录结构

```
Project/
├── backend/               # FastAPI 后端（uv + pyproject.toml）
│   └── app/
│       ├── main.py        # 入口 + /health
│       ├── core/          # 配置分层、日志、安全
│       ├── api/           # REST/WS 路由 + 依赖注入
│       ├── db/            # SQLAlchemy
│       ├── models/        # Pydantic schema
│       ├── agent/         # LangGraph 编排
│       ├── capabilities/  # workflow / rag / graphrag
│       ├── retrieval/     # 混合检索 + rerank
│       └── platform/      # 多租户 / RBAC / 监控 / 审计
├── frontend/              # Vue 3 前端
├── models/                # 本地模型缓存（bge-base-zh-v1.5，HF cache 格式）
└── README.md              # 项目说明
```

## 快速开始

### 后端

```bash
cd backend
uv sync                              # 安装依赖
uv run python -m uvicorn app.main:app --reload # http://127.0.0.1:8000
# GET /health           存活探针
# GET /api/v1/health    就绪探针
# /docs                 接口文档
```

### 前端

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

## AI Agent 工程能力

项目在原有 LangGraph 业务编排之外，增加了一套可离线测试、供应商无关的 Agent Harness：

- **AI 工具使用**：工具白名单、JSON Schema 参数校验、统一成功/失败结果，不使用 `eval` 或动态导入。
- **Agent Loop**：`Observe -> Decide -> Act -> Guard -> Answer`，带最大步数、重复调用检测、异常隔离和可机读 trace。trace 记录 Planner/工具耗时、终止原因和 Prompt 版本，便于定位失败步骤。
- **Harness / Context Engineering**：上下文按优先级装配，对整体与单条工具输出设置硬预算；每次运行返回 included/dropped 来源与预算使用量。
- **Prompt Engineering**：采用“角色—目标—决策策略—安全边界—完成标准”结构；系统指令、业务上下文、用户输入和 scratchpad 分层，Prompt 带版本号，不可信输入会进行边界转义。
- **Eval-driven 迭代**：将工具选择、参数正确性、不安全动作率、Prompt 结构和上下文预算都纳入离线回归。

用户只需访问原有 `POST /api/v1/chat` 或 `/chat/stream`。LangGraph 负责统一会话状态与路由：已提供物流单号的实时查询会在 `execute` 节点内交给 LLM tool-calling Loop；缺少单号的多轮收集走 Workflow；政策问答走 RAG。地址修改、退货申请等有副作用操作仍由声明式 Workflow 处理。

关键实现位于 `backend/app/agent/{tools,loop,context,prompting}.py`。原有 LangGraph 负责会话级状态和能力路由，Agent Loop 负责一个能力内的安全工具决策，两者职责分离。

离线示例不需要 API Key：

```bash
cd backend
uv run python -m examples.agent_loop_demo
uv run pytest tests/test_agent_loop.py -q
```

管理员可访问 `GET /api/v1/evals/agent` 查看离线 Agent 回归报告，其中包含任务成功率、工具选择准确率、参数准确率和不安全动作率。
另可访问 `GET /api/v1/evals/prompt` 查看 Prompt 版本、指令分层、注入边界和上下文预算的确定性回归报告。两类报告都明确区分“Harness 结构正确性”与“真实模型效果”，避免夸大评测结论。

### 岗位要求与项目证据

| 岗位要求 | 项目中的可验证证据 |
|---|---|
| 熟悉 AI 产品使用逻辑与场景 | 智能客服中的 Workflow / RAG / GraphRAG / Agent 分层路由，不同任务选择不同能力 |
| Harness Engineering | 工具白名单、Schema 校验、租户边界、超时/异常收口、重复调用和最大步数 guard |
| Loop Engineering | `Observe -> Decide -> Act -> Guard -> Answer` 及可机读步骤 trace |
| Context Engineering | 优先级装配、单项/总量预算、included/dropped 可观测数据 |
| Prompt Engineering | v2 结构化 Prompt、指令/数据隔离、边界转义、版本化和离线回归 |

## 中间件（本机裸跑，无需 Docker）

| 中间件 | 本机方案 | 说明 |
|---|---|---|
| 数据库 | SQLite（默认） | 阶段 9 换 MySQL |
| Redis | 开发期用 MemorySaver 替代 | checkpoint 后端 |
| Neo4j | Neo4j Desktop / 社区版 | `bolt://localhost:7687` |
| Chroma | pip 包进程内运行 | 无需独立服务 |
| 向量模型 | 本地 `models/` 缓存 | bge-base-zh-v1.5，加载不联网 |

配置集中见 [backend/app/core/config.py](backend/app/core/config.py)，通过 `.env` 覆盖（见 [backend/.env.example](backend/.env.example)）。

生产模式会拒绝默认 JWT 密钥、内存 checkpoint 和进程内限流。Docker Compose 使用 Redis Stack 同时承载 RedisSaver 与分布式滑动窗口限流，并为 Redis/Neo4j 配置了 healthcheck。前端不再嵌入 `VITE_DEV_TOKEN` 或默认管理员身份。
