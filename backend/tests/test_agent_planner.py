from types import SimpleNamespace

from app.agent.business_tools import build_readonly_business_tools
from app.agent.loop import AgentDecision, AgentLoop
from app.agent.planner import ToolCallingPlanner
from app.agent.service import should_run_readonly_agent
from app.core.config import BusinessIntegrationSettings
from app.evals.agent_runner import run_agent_harness_evaluation
from app.services.business_gateway import BusinessGateway, DemoBusinessProvider


class FakeModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.bound_tools = None

    def bind_tools(self, tools, tool_choice="auto"):
        self.bound_tools = tools
        assert tool_choice == "auto"
        return self

    def invoke(self, prompt):
        return next(self.responses)


def test_real_planner_adapter_parses_structured_tool_call():
    model = FakeModel([SimpleNamespace(
        tool_calls=[{"name": "query_logistics", "args": {"tracking_no": "SF12345678"}}],
        content="",
    )])
    decision = ToolCallingPlanner(model).decide("prompt", [{"type": "function"}])
    assert decision == AgentDecision(
        "tool", "query_logistics", {"tracking_no": "SF12345678"}
    )
    assert model.bound_tools


def test_business_tool_uses_existing_gateway():
    gateway = BusinessGateway(
        DemoBusinessProvider(), BusinessIntegrationSettings(provider="demo")
    )
    result = build_readonly_business_tools(gateway).execute(
        "query_logistics", {"tracking_no": "SF12345678"}
    )
    assert result.ok
    assert result.output["status"] == "沙盒运输中"


def test_business_tool_rejects_short_tracking_number():
    gateway = BusinessGateway(
        DemoBusinessProvider(), BusinessIntegrationSettings(provider="demo")
    )
    result = build_readonly_business_tools(gateway).execute(
        "query_logistics", {"tracking_no": "123"}
    )
    assert not result.ok
    assert "长度不足" in result.error


def test_grounding_guard_rejects_answer_before_tool():
    class Planner:
        def decide(self, prompt, tools):
            return AgentDecision("final", answer="明天送达")

    result = AgentLoop(Planner(), build_readonly_business_tools(), require_tool=True).run("查物流")
    assert result.status == "ungrounded_final"


def test_agent_eval_exposes_required_metrics():
    report = run_agent_harness_evaluation()
    assert report["task_success_rate"] == 1.0
    assert report["tool_dispatch_conformance"] == 1.0
    assert report["argument_dispatch_conformance"] == 1.0
    assert report["unsafe_action_rate"] == 0.0
    assert "不表示模型" in report["scope_note"]


def test_readonly_agent_only_handles_complete_logistics_query():
    assert should_run_readonly_agent("查物流 SF12345678")
    assert not should_run_readonly_agent("查物流")
    assert not should_run_readonly_agent("退货政策 SF12345678")
