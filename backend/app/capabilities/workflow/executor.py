"""流程执行器：按步骤类型分发（action/collect/set_slot/condition/link）。

单轮内沿步骤推进，直到「需要用户输入」（collect 询问）或「流程结束」。
支持流程中断（切换新流程，压栈）与恢复（子流程结束，弹栈回到上一层）。
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.state import AgentState
from app.capabilities.workflow.flow import Flow, FlowStep, match_flow
from app.capabilities.workflow.slot_filling import (
    Correction,
    CorrectionAction,
    extract_value,
    locate_slot,
)
from app.capabilities.workflow.stack import DialogueStack, FlowFrame

# 动作处理器：action 步骤的副作用执行（阶段 2 Mock，阶段 9 接 Repository）
ActionHandler = Callable[[str, dict[str, Any], str], str]

_CONDITION_RE = re.compile(r"^(?P<slot>\w+)\s*(?P<op>==|!=|>=|<=|>|<)\s*(?P<value>.+)$")
_TRACKING_RE = re.compile(r"\b[A-Za-z]{0,3}\d{8,20}\b")
_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")


def extract_inline_slots(text: str) -> dict[str, str]:
    """从自然语言中提取常见业务字段，减少机械式逐槽追问。"""
    value = (text or "").strip()
    slots: dict[str, str] = {}
    tracking = _TRACKING_RE.search(value)
    phone = _PHONE_RE.search(value)
    if tracking:
        slots["tracking_no"] = tracking.group(0)
    if phone:
        slots["receiver_phone"] = phone.group(0)
    for marker, slot in (("收货人", "receiver_name"), ("姓名", "receiver_name")):
        match = re.search(rf"{marker}(?:是|为|叫)?([^，。,\s]{2,20})", value)
        if match:
            slots[slot] = match.group(1)
            break
    address = re.search(r"(?:详细地址|收货地址|地址)(?:是|为)?([^。！？!?]+)", value)
    if address:
        slots["receiver_address"] = address.group(1).strip(" ，,：:")
    reason = re.search(r"(?:原因|因为)(?:是|为)?([^。！？!?]+)", value)
    if reason:
        slots["reason"] = reason.group(1).strip(" ，,：:")
    if "生鲜" in value:
        slots["goods_type"] = "生鲜"
    elif "普通" in value:
        slots["goods_type"] = "普通"
    return slots


def default_action_handler(action: str, slots: dict[str, Any], flow_id: str) -> str:
    """Mock 动作：阶段 9 替换为业务 Repository 调用。"""
    return f"已为您完成「{action}」（占位，阶段 9 接业务数据）。"


def _insert_answer(user_input: str) -> str:
    """轻量问题/闲聊的插入回答（占位，阶段 6 接入 RAG/闲聊）。"""
    return "好的，我先回答您的问题（占位，阶段 6 接入 RAG/闲聊）。"


def evaluate_condition(expression: str, slots: dict[str, Any]) -> bool:
    """安全地求值条件表达式（不使用 eval）。

    支持 `<slot> <op> <literal>`，op ∈ {==, !=, >=, <=, >, <}；
    literal 支持字符串（引号）、数字、true/false/null。
    """
    expr = (expression or "").strip()
    m = _CONDITION_RE.match(expr)
    if not m:
        raise ValueError(f"无法解析条件表达式: {expression}")

    slot_value = slots.get(m.group("slot"))
    literal = _parse_literal(m.group("value").strip())
    op = m.group("op")

    if op == "==":
        return slot_value == literal
    if op == "!=":
        return slot_value != literal

    # 数值比较
    try:
        slot_num = float(slot_value)
        lit_num = float(literal)
    except (TypeError, ValueError):
        return False
    if op == ">":
        return slot_num > lit_num
    if op == "<":
        return slot_num < lit_num
    if op == ">=":
        return slot_num >= lit_num
    if op == "<=":
        return slot_num <= lit_num
    return False


def _parse_literal(raw: str) -> Any:
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


@dataclass
class _RunResult:
    response: str
    finished: bool
    interrupt_flow: str | None = None  # 非空表示需要压栈中断到该流程


class FlowExecutor:
    """按声明式 Flow 执行多轮业务办理。"""

    def __init__(self, flows: dict[str, Flow], action_handler: ActionHandler | None = None) -> None:
        self.flows = flows
        self.action_handler = action_handler or default_action_handler

    def handle(self, state: AgentState) -> dict[str, Any]:
        """从 agent state 恢复对话栈并推进一轮。"""
        stack = DialogueStack.from_list(state.get("flow_stack", []))
        user_input = (state.get("user_input") or "").strip()

        if stack.is_empty():
            flow = match_flow(user_input, self.flows)
            if flow is None:
                return {"response": "未识别到可办理的业务，请描述您的需求。"}
            stack.push_flow(flow.id)
            stack.top().slots.update(extract_inline_slots(user_input))
            result = self._run(flow, stack.top(), user_input=None, consume_input=False)
        else:
            frame = stack.top()
            flow = self.flows.get(frame.flow_id)
            if flow is None:
                return self._reset("流程配置缺失，请稍后再试。")
            result = self._run(flow, frame, user_input=user_input, consume_input=True)
            # 意图漂移：新业务流程 → 压栈中断，立即执行新流程首步
            if result.interrupt_flow:
                stack.push_flow(result.interrupt_flow)
                new_flow = self.flows.get(result.interrupt_flow)
                if new_flow is None:
                    return self._reset("流程配置缺失，请稍后再试。")
                result = self._run(new_flow, stack.top(), user_input=None, consume_input=False)

        if result.finished:
            stack.pop_flow()

        top = stack.top()
        return {
            "response": result.response,
            "flow_stack": stack.to_list(),
            "active_flow": top.flow_id if top else None,
            "slots": top.slots if top else {},
        }

    def _reset(self, response: str) -> dict[str, Any]:
        return {"response": response, "flow_stack": [], "active_flow": None, "slots": {}}

    def _run(
        self, flow: Flow, frame: FlowFrame, user_input: str | None, consume_input: bool
    ) -> _RunResult:
        """在单轮内沿步骤推进，直到需要用户输入或流程结束。"""
        # 延迟导入：router 依赖 slot_filling（经 workflow 包），顶层导入会形成循环
        from app.agent.router import TurnAction, decide_active_flow

        step = flow.step_by_id(frame.current_step) if frame.current_step else flow.first_step()
        input_consumed = False

        while step is not None:
            if step.type == "collect":
                if step.slot in frame.slots:
                    step = self._advance(flow, step, frame)
                    continue
                if not consume_input or input_consumed:
                    frame.current_step = step.id
                    return _RunResult(response=self._prompt(step), finished=False)

                # PRD BR-010：活跃流程下判定本轮输入（纠错 → 填槽 → 漂移）
                new_flow = match_flow(user_input, self.flows)
                if new_flow is not None and new_flow.id == flow.id:
                    new_flow = None  # 匹配到当前流程本身，不算中断

                slot_input = extract_inline_slots(user_input).get(step.slot, user_input)
                decision = decide_active_flow(
                    slot_input, step.validate, new_flow.id if new_flow else None
                )

                if decision.action == TurnAction.FILL:
                    frame.slots[step.slot] = (slot_input or "").strip()
                    frame.last_slot = step.slot
                    input_consumed = True
                    step = self._advance(flow, step, frame)
                    continue

                if decision.action == TurnAction.CORRECT:
                    result = self._apply_correction(
                        flow, frame, step, user_input, decision.correction
                    )
                    if result is not None:
                        return result
                    input_consumed = True
                    step = self._advance(flow, step, frame)
                    continue

                if decision.action == TurnAction.CANCEL:
                    frame.current_step = None
                    return _RunResult(response="已取消当前流程。", finished=True)

                if decision.action == TurnAction.INTERRUPT:
                    frame.current_step = step.id  # 保持当前槽位，恢复时继续
                    return _RunResult(
                        response="", finished=False, interrupt_flow=decision.new_flow_id
                    )

                if decision.action == TurnAction.REPROMPT:
                    frame.current_step = step.id
                    return _RunResult(
                        response=self._prompt(step) + "（格式有误，请重新填写）",
                        finished=False,
                    )

                # INSERT：轻量问题，插入处理，不改变流程栈
                frame.current_step = step.id
                return _RunResult(
                    response=_insert_answer(user_input) + self._prompt(step),
                    finished=False,
                )

            if step.type == "set_slot":
                frame.slots[step.slot] = step.value
                step = self._advance(flow, step, frame)
                continue

            if step.type == "action":
                response = self.action_handler(step.action, dict(frame.slots), flow.id)
                nxt = self._next_step(flow, step)
                if nxt is None:
                    frame.current_step = None
                    return _RunResult(response=response, finished=True)
                step = nxt
                frame.current_step = nxt.id
                continue

            if step.type == "condition":
                truthy = evaluate_condition(step.condition, frame.slots)
                target = step.then if truthy else step.else_
                step = flow.step_by_id(target) if target else self._next_step(flow, step)
                frame.current_step = step.id if step else None
                continue

            if step.type == "link":
                step = flow.step_by_id(step.target) if step.target else None
                frame.current_step = step.id if step else None
                continue

            raise ValueError(f"未知步骤类型: {step.type}")

        frame.current_step = None
        return _RunResult(response="已为您处理完成。", finished=True)

    def _prompt(self, step: FlowStep) -> str:
        return step.prompt or f"请提供{step.slot}"

    def _next_step(self, flow: Flow, step: FlowStep) -> FlowStep | None:
        for i, s in enumerate(flow.steps):
            if s.id == step.id:
                return flow.steps[i + 1] if i + 1 < len(flow.steps) else None
        return None

    def _advance(self, flow: Flow, step: FlowStep, frame: FlowFrame) -> FlowStep | None:
        nxt = self._next_step(flow, step)
        frame.current_step = nxt.id if nxt else None
        return nxt

    def _apply_correction(
        self,
        flow: Flow,
        frame: FlowFrame,
        step: FlowStep,
        user_input: str,
        correction: Correction,
    ) -> _RunResult | None:
        """处理纠错（CORRECT/REWIND/SKIP）；返回 None 表示已消费输入并前进。"""
        slot_aliases = self._slot_aliases(flow)
        target = locate_slot(user_input, slot_aliases, frame.last_slot or step.slot)

        if correction.action == CorrectionAction.SKIP:
            if not step.optional:
                frame.current_step = step.id
                return _RunResult(
                    response=self._prompt(step) + "（该信息为必填项，无法跳过）",
                    finished=False,
                )
            return None  # 跳过可选槽位：前进

        if correction.action == CorrectionAction.REWIND:
            frame.slots.pop(target, None)
            target_step = self._collect_step_for_slot(flow, target) or step
            frame.current_step = target_step.id
            return _RunResult(response=self._prompt(target_step), finished=False)

        # CORRECT：仅更新目标槽位，其余保持不变
        value = extract_value(correction.rest, slot_aliases.get(target, []))
        if value is None:
            frame.slots.pop(target, None)
            target_step = self._collect_step_for_slot(flow, target) or step
            frame.current_step = target_step.id
            return _RunResult(response="请重新填写" + self._prompt(target_step), finished=False)

        frame.slots[target] = value
        frame.last_slot = target
        if target == step.slot:
            return None  # 纠正的是当前槽位 → 视为已填，前进
        frame.current_step = step.id
        return _RunResult(response=f"已更正，{value}。" + self._prompt(step), finished=False)

    def _slot_aliases(self, flow: Flow) -> dict[str, list[str]]:
        return {s.slot: s.aliases for s in flow.collect_steps() if s.slot}

    def _collect_step_for_slot(self, flow: Flow, slot: str) -> FlowStep | None:
        for s in flow.collect_steps():
            if s.slot == slot:
                return s
        return None
