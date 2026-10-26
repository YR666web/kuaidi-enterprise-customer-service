"""将现有 BusinessGateway 以受控 AI 工具形式暴露。"""

from app.agent.tools import ToolRegistry, ToolSpec
from app.services.business_gateway import BusinessGateway, build_business_gateway


def build_readonly_business_tools(gateway: BusinessGateway | None = None) -> ToolRegistry:
    """只注册无副作用工具；写操作仍交给声明式 Workflow 处理。"""
    gateway = gateway or build_business_gateway()
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="query_logistics",
            description=(
                "根据客户提供的物流单号查询可核验状态。"
                "只能使用用户明确提供的单号；不得猜测。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "tracking_no": {
                        "type": "string",
                        "description": "8-23 位字母数字物流单号",
                        "minLength": 8,
                        "maxLength": 23,
                    }
                },
                "required": ["tracking_no"],
                "additionalProperties": False,
            },
            handler=gateway.track,
        )
    )
    return registry
