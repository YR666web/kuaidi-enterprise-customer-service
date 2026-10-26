"""可被 API 调用的真实 Agent 服务。"""

import re

from app.agent.business_tools import build_readonly_business_tools
from app.agent.context import ContextBuilder, ContextItem
from app.agent.loop import AgentLoop, LoopResult
from app.agent.planner import ToolCallingPlanner
from app.core.config import settings
from app.llm import get_fast_model, has_llm


class AgentUnavailableError(RuntimeError):
    """模型未配置时的可预期错误。"""


_TRACKING_RE = re.compile(r"\b[A-Za-z]{0,3}\d{8,20}\b")
_LOGISTICS_MARKERS = ("物流", "快递", "运单", "包裹")


def should_run_readonly_agent(query: str) -> bool:
    """只将已经具备完整单号的实时查询交给自主工具决策。"""
    return bool(_TRACKING_RE.search(query)) and any(
        marker in query for marker in _LOGISTICS_MARKERS
    )


def run_readonly_agent(query: str, tenant_id: str) -> LoopResult:
    """执行只读业务 Agent，由 LangGraph execute 节点调用。"""
    if not has_llm():
        raise AgentUnavailableError("未配置 LLM__API_KEY，真实 Agent Planner 不可用")
    context = [
        ContextItem(
            "security_policy",
            f"已验证租户={tenant_id}。仅允许调用工具列表中的只读能力。",
            priority=100,
        ),
        ContextItem(
            "provider_policy",
            f"当前业务供应商模式={settings.business_integration.provider}。"
            "local 模式未接入真实轨迹时必须明确说明无法核验。",
            priority=90,
        ),
    ]
    loop = AgentLoop(
        ToolCallingPlanner(get_fast_model()),
        build_readonly_business_tools(),
        max_steps=settings.agent.max_actions,
        context_builder=ContextBuilder(max_chars=4_000, max_item_chars=1_500),
        require_tool=True,
    )
    return loop.run(query, context)
