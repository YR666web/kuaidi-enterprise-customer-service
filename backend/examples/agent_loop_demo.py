"""离线可运行的工具调用 + Agent Loop 示例。"""

from app.agent.context import ContextItem
from app.agent.loop import AgentDecision, AgentLoop
from app.agent.tools import ToolRegistry, ToolSpec


class DemoPlanner:
    def __init__(self) -> None:
        self.turn = 0

    def decide(self, prompt, tools):
        self.turn += 1
        if self.turn == 1:
            return AgentDecision("tool", "query_logistics", {"tracking_no": "SF123456"})
        return AgentDecision("final", answer="SF123456 正在运输中，最新节点：杭州转运中心。")


def main() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="query_logistics",
            description="按物流单号查询可核验的物流节点",
            parameters={
                "type": "object",
                "properties": {"tracking_no": {"type": "string"}},
                "required": ["tracking_no"],
                "additionalProperties": False,
            },
            handler=lambda tracking_no: {
                "tracking_no": tracking_no,
                "status": "in_transit",
                "latest_event": "杭州转运中心",
            },
        )
    )
    result = AgentLoop(DemoPlanner(), registry).run(
        "帮我查 SF123456 的物流",
        [ContextItem("tenant_policy", "只能查询当前租户订单", priority=100)],
    )
    print(result.answer)
    print(result.trace)


if __name__ == "__main__":
    main()
