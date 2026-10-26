"""LangGraph `StateGraph` 构建 + checkpoint 接入。

checkpoint 策略：
- 开发期：`MemorySaver`（进程内快照）；
- 生产：`RedisSaver`（延迟导入，需额外安装 `langgraph-checkpoint-redis`）。

支持：
- 断线恢复：同一 `thread_id` 续跑，历史不丢；
- 时间回溯：`graph.get_state_history(config)` 取任意历史快照。
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent import nodes
from app.agent.state import AgentState
from app.core.config import settings


def get_checkpointer(backend: str | None = None) -> BaseCheckpointSaver:
    """构建 checkpoint 后端（默认 MemorySaver，接口预留 RedisSaver 切换）。"""
    backend = backend or settings.agent.checkpoint_backend

    if backend == "memory":
        if settings.app.environment == "production":
            raise RuntimeError("生产环境禁止 MemorySaver，请设置 AGENT__CHECKPOINT_BACKEND=redis")
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    if backend == "redis":
        # 延迟导入：避免骨架阶段强依赖 langgraph-checkpoint-redis
        try:
            from langgraph.checkpoint.redis import RedisSaver
        except ImportError as exc:
            raise ImportError(
                "Redis checkpoint 需要额外安装 langgraph-checkpoint-redis；"
                "开发期请使用 memory 后端。"
            ) from exc
        # from_conn_string() 返回上下文管理器，不能直接作为 graph checkpointer。
        # 服务进程生命周期由 RedisSaver 自身连接池管理；启动期会在 main.lifespan 执行 setup。
        return RedisSaver(settings.redis.url)

    raise ValueError(f"未知的 checkpoint 后端: {backend}")


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """构建并编译状态机。

    拓扑：START → understand → execute → respond → END
    降级链（route → execute → degrade → fallback + guard）由 execute 内的
    router.FallbackChain 承载。
    """
    builder = StateGraph(AgentState)

    builder.add_node("understand", nodes.understand_node)
    builder.add_node("execute", nodes.execute_node)
    builder.add_node("respond", nodes.respond_node)

    builder.add_edge(START, "understand")
    builder.add_edge("understand", "execute")
    builder.add_edge("execute", "respond")
    builder.add_edge("respond", END)

    return builder.compile(checkpointer=checkpointer or get_checkpointer())
