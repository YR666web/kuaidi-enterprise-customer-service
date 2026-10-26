"""将 LangChain/OpenAI 兼容模型的 structured tool call 适配为 AgentDecision。"""

import json
from typing import Any

from app.agent.loop import AgentDecision


class ToolCallingPlanner:
    """真实模型 Planner；不执行工具，只负责产生受约束决策。"""

    def __init__(self, model: Any) -> None:
        self.model = model

    def decide(self, prompt: str, tools: list[dict[str, Any]]) -> AgentDecision:
        response = self.model.bind_tools(tools, tool_choice="auto").invoke(prompt)
        calls = getattr(response, "tool_calls", None) or []
        if calls:
            call = calls[0]
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            arguments = (
                call.get("args", {})
                if isinstance(call, dict)
                else getattr(call, "args", {})
            )
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    return AgentDecision("invalid")
            if not isinstance(arguments, dict):
                return AgentDecision("invalid")
            return AgentDecision("tool", tool_name=name, arguments=arguments)
        content = str(getattr(response, "content", "") or "").strip()
        return AgentDecision("final", answer=content)
