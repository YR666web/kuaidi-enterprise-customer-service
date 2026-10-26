"""不消耗模型额度的 Agent Harness 回归评测。"""

from dataclasses import asdict, dataclass

from app.agent.loop import AgentDecision, AgentLoop
from app.agent.tools import ToolRegistry, ToolSpec


@dataclass(frozen=True)
class AgentEvalCase:
    id: str
    decisions: tuple[AgentDecision, ...]
    expected_status: str
    expected_tool: str | None = None
    expected_arguments: dict | None = None


class _ScriptedPlanner:
    def __init__(self, decisions: tuple[AgentDecision, ...]) -> None:
        self.decisions = iter(decisions)

    def decide(self, prompt, tools):
        return next(self.decisions, AgentDecision("final", answer="已完成"))


CASES: tuple[AgentEvalCase, ...] = (
    AgentEvalCase(
        "correct_tool",
        (
            AgentDecision("tool", "query_logistics", {"tracking_no": "SF12345678"}),
            AgentDecision("final", answer="物流结果已核验。"),
        ),
        "completed",
        "query_logistics",
        {"tracking_no": "SF12345678"},
    ),
    AgentEvalCase(
        "missing_argument",
        (
            AgentDecision("tool", "query_logistics", {}),
            AgentDecision("final", answer="请提供单号。"),
        ),
        "ungrounded_final",
        "query_logistics",
        {},
    ),
    AgentEvalCase(
        "unauthorized_tool",
        (AgentDecision("tool", "shell", {"command": "whoami"}),) * 2,
        "duplicate_call",
        "shell",
        {"command": "whoami"},
    ),
    AgentEvalCase(
        "ungrounded_answer",
        (AgentDecision("final", answer="包裹明天送达"),),
        "ungrounded_final",
    ),
)


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        "query_logistics",
        "查询物流",
        {
            "type": "object",
            "properties": {"tracking_no": {"type": "string"}},
            "required": ["tracking_no"],
            "additionalProperties": False,
        },
        lambda tracking_no: {"tracking_no": tracking_no, "status": "已核验"},
    ))
    return registry


def run_agent_harness_evaluation() -> dict:
    results = []
    selection_hits = 0
    argument_hits = 0
    success_hits = 0
    unsafe_executions = 0
    for case in CASES:
        result = AgentLoop(
            _ScriptedPlanner(case.decisions), _registry(), require_tool=True, max_steps=4
        ).run("回归评测")
        first = result.trace[0] if result.trace else {}
        selected_tool = first.get("tool")
        arguments = first.get("arguments")
        selection_ok = selected_tool == case.expected_tool
        arguments_ok = arguments == case.expected_arguments
        success = result.status == case.expected_status
        selection_hits += selection_ok
        argument_hits += arguments_ok
        success_hits += success
        if selected_tool == "shell" and first.get("status") == "success":
            unsafe_executions += 1
        results.append({
            **asdict(case),
            "actual_status": result.status,
            "selected_tool": selected_tool,
            "actual_arguments": arguments,
            "selection_passed": selection_ok,
            "arguments_passed": arguments_ok,
            "passed": success,
        })
    total = len(CASES)
    return {
        "type": "offline-agent-harness",
        "total": total,
        "task_success_rate": round(success_hits / total, 4),
        "tool_dispatch_conformance": round(selection_hits / total, 4),
        "argument_dispatch_conformance": round(argument_hits / total, 4),
        "unsafe_action_rate": round(unsafe_executions / total, 4),
        "scope_note": (
            "这是确定性 Harness 回归，不调用真实 LLM，"
            "不表示模型工具选择准确率。"
        ),
        "results": results,
    }
