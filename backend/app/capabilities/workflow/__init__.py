"""Workflow 多轮业务办理能力。

对外暴露 build_workflow_capability()，返回供 agent CAPABILITIES 注册的
`workflow(state) -> dict` 能力函数。
"""

from collections.abc import Callable
from typing import Any

from app.agent.state import AgentState
from app.capabilities.workflow.executor import ActionHandler, FlowExecutor
from app.capabilities.workflow.flow import Flow, load_flows
from app.core.config import settings
from app.repositories import build_action_handler


def build_workflow_capability(
    flows_dir: str | None = None,
    action_handler: ActionHandler | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """构建 workflow 能力函数。flows_dir 默认取配置；action_handler 默认 Mock。"""
    flows: dict[str, Flow] = load_flows(flows_dir or settings.workflow.flows_dir)
    executor = FlowExecutor(flows, action_handler=action_handler or build_action_handler())

    def workflow(state: AgentState) -> dict[str, Any]:
        return executor.handle(state)

    return workflow
