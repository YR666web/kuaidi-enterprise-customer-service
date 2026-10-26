"""供应商无关的 Agent Loop：Observe -> Decide -> Act -> Guard -> Answer。"""

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

from app.agent.context import ContextBuilder, ContextItem
from app.agent.prompting import PROMPT_VERSION, PromptEnvelope
from app.agent.tools import ToolRegistry


@dataclass(frozen=True)
class AgentDecision:
    kind: str  # tool | final
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    answer: str = ""


class Planner(Protocol):
    def decide(self, prompt: str, tools: list[dict[str, Any]]) -> AgentDecision: ...


@dataclass
class LoopResult:
    answer: str
    status: str
    steps: int
    trace: list[dict[str, Any]]
    prompt_version: str = PROMPT_VERSION
    context_stats: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


class AgentLoop:
    def __init__(
        self,
        planner: Planner,
        tools: ToolRegistry,
        *,
        max_steps: int = 6,
        context_builder: ContextBuilder | None = None,
        require_tool: bool = False,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps 必须为正数")
        self.planner = planner
        self.tools = tools
        self.max_steps = max_steps
        self.context_builder = context_builder or ContextBuilder()
        self.require_tool = require_tool

    def run(self, user_input: str, context: list[ContextItem] | None = None) -> LoopResult:
        started = perf_counter()
        window = self.context_builder.build(context or [])
        context_stats = {
            "included": window.included,
            "dropped": window.dropped,
            "used_chars": window.used_chars,
            "max_chars": self.context_builder.max_chars,
        }
        observations: list[str] = []
        trace: list[dict[str, Any]] = []
        seen_calls: set[str] = set()
        successful_tool_calls = 0
        for step in range(1, self.max_steps + 1):
            prompt = PromptEnvelope(
                user_input=user_input,
                context=window.text,
                scratchpad="\n".join(observations) or "无",
            ).render()
            plan_started = perf_counter()
            decision = self.planner.decide(prompt, self.tools.schemas())
            planner_ms = round((perf_counter() - plan_started) * 1000, 3)
            if decision.kind == "final":
                if self.require_tool and successful_tool_calls == 0:
                    return self._result(
                        "未获得可核验的工具结果，已拒绝直接生成业务事实。",
                        "ungrounded_final",
                        step,
                        trace,
                        context_stats,
                        started,
                    )
                answer = decision.answer.strip()
                if not answer:
                    return self._result(
                        "无法生成有效回复。",
                        "invalid_final",
                        step,
                        trace,
                        context_stats,
                        started,
                    )
                trace.append({"step": step, "action": "final", "planner_ms": planner_ms})
                return self._result(answer, "completed", step, trace, context_stats, started)
            if decision.kind != "tool" or not decision.tool_name:
                return self._result(
                    "执行计划无效，已安全终止。",
                    "invalid_decision",
                    step,
                    trace,
                    context_stats,
                    started,
                )

            fingerprint = json.dumps(
                [decision.tool_name, decision.arguments], sort_keys=True, ensure_ascii=False
            )
            if fingerprint in seen_calls:
                trace.append({"step": step, "tool": decision.tool_name, "status": "duplicate"})
                return self._result(
                    "检测到重复工具调用，已安全终止。",
                    "duplicate_call",
                    step,
                    trace,
                    context_stats,
                    started,
                )
            seen_calls.add(fingerprint)

            tool_started = perf_counter()
            result = self.tools.execute(decision.tool_name, decision.arguments)
            tool_ms = round((perf_counter() - tool_started) * 1000, 3)
            if result.ok:
                successful_tool_calls += 1
            trace.append(
                {
                    "step": step,
                    "tool": decision.tool_name,
                    "arguments": decision.arguments,
                    "status": "success" if result.ok else "error",
                    "error": result.error,
                    "planner_ms": planner_ms,
                    "tool_ms": tool_ms,
                }
            )
            payload = result.output if result.ok else {"error": result.error}
            observations.append(
                f"<tool_result name={decision.tool_name!r}>"
                f"{json.dumps(payload, ensure_ascii=False, default=str)}"
                "</tool_result>"
            )
        return self._result(
            "已达单轮最大动作数，请稍后重试或转人工。",
            "max_steps",
            self.max_steps,
            trace,
            context_stats,
            started,
        )

    @staticmethod
    def _result(
        answer: str,
        status: str,
        steps: int,
        trace: list[dict[str, Any]],
        context_stats: dict[str, Any],
        started: float,
    ) -> LoopResult:
        """统一收口，保证成功、降级和 guard 终止都带可比较的运行元数据。"""
        return LoopResult(
            answer=answer,
            status=status,
            steps=steps,
            trace=trace,
            context_stats=context_stats,
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )
