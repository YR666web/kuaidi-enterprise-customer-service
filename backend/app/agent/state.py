"""对话编排状态定义（LangGraph `StateGraph` 的 State）。

字段语义：
- `messages` 用 `add_messages` 追加（完整对话历史，随 checkpoint 持久化）；
- 其余字段默认覆盖（overwrite）语义，各节点返回的 partial state 会合并更新。
"""

from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class Intent(StrEnum):
    """意图类型（路由决策的依据）。"""

    WORKFLOW = "workflow"  # 多轮业务办理
    RAG = "rag"            # 知识问答
    GRAPHRAG = "graphrag"  # 图谱问答
    CHITCHAT = "chitchat"  # 闲聊
    FALLBACK = "fallback"  # 兜底


class AgentState(TypedDict, total=False):
    """对话编排状态。

    `total=False` 表示所有字段可缺省，各节点按需构建/更新。
    """

    # —— 会话与输入 ——
    session_id: str
    tenant_id: str  # checkpoint、检索和业务数据均以租户为边界
    messages: Annotated[list[BaseMessage], add_messages]  # 完整对话历史（追加）
    user_input: str  # 当前轮用户原始输入
    user_id: str | None  # GraphRAG 用户隔离条件

    # —— 意图识别（understand 产出）——
    intent: Intent  # 当前识别意图
    intent_confidence: float  # 意图置信度

    # —— 多轮业务办理（阶段 3 使用）——
    slots: dict[str, Any]  # 当前流程已填槽位
    active_flow: str | None  # 活跃流程 ID（栈顶帧的 flow_id）
    flow_stack: list[dict[str, Any]]  # 对话栈（序列化 FlowFrame，LIFO；中断/恢复）

    # —— 路由与降级（route / execute 使用）——
    next_capability: str | None  # 待执行能力（route 决定、execute 消费）
    degradation_path: list[str]  # 已尝试（失败）的能力序列
    tool_trace: list[dict[str, Any]]  # 工具调用轨迹
    last_error: str | None  # 最近一次执行错误

    # —— 循环保护（guard 使用）——
    action_count: int  # 本轮动作计数

    # —— 输出（execute / respond 产出）——
    response: str  # 最终回复文本
    citations: list[str]  # 引用溯源
    stream_response: bool  # SSE 时延迟生成 LLM 回复，以便逐 token 输出
    response_tier: str  # fast | reasoning，选择 Flash 或 V4 Pro
    stream_plan: dict[str, Any]  # RAG / 已核验业务结果的节点内流式生成计划
