"""槽位纠错测试（PRD 10.1.1 场景二 + 跳过/取消/重新）。"""

from app.capabilities.workflow.executor import FlowExecutor
from app.capabilities.workflow.flow import Flow, FlowStep
from app.capabilities.workflow.slot_filling import (
    CorrectionAction,
    extract_value,
    locate_slot,
    recognize_correction,
)


def _run_turns(executor, turns):
    state = {"flow_stack": [], "active_flow": None, "slots": {}}
    results = []
    for text in turns:
        state["user_input"] = text
        out = executor.handle(state)
        state["flow_stack"] = out["flow_stack"]
        state["active_flow"] = out["active_flow"]
        state["slots"] = out["slots"]
        results.append(out)
    return state, results


def _address_flow() -> Flow:
    return Flow(
        id="modify_address",
        name="修改收货地址",
        triggers=["改地址"],
        steps=[
            FlowStep(
                id="ask_name", type="collect", slot="receiver_name",
                prompt="请提供姓名", aliases=["姓名"],
            ),
            FlowStep(
                id="ask_phone", type="collect", slot="receiver_phone",
                prompt="请提供手机号", validate="phone", aliases=["手机号", "电话"],
            ),
            FlowStep(
                id="ask_address", type="collect", slot="receiver_address",
                prompt="请提供地址", aliases=["地址"],
            ),
        ],
    )


# —— 纠错信号识别 ——
def test_recognize_correction_signals():
    assert recognize_correction("不对，是139").action == CorrectionAction.CORRECT
    assert recognize_correction("不是这个").action == CorrectionAction.CORRECT
    assert recognize_correction("改成139").action == CorrectionAction.CORRECT
    assert recognize_correction("重新填").action == CorrectionAction.REWIND
    assert recognize_correction("跳过").action == CorrectionAction.SKIP
    assert recognize_correction("取消").action == CorrectionAction.CANCEL
    assert recognize_correction("算了").action == CorrectionAction.CANCEL
    assert recognize_correction("13800001111") is None  # 正常值非纠错


def test_extract_value():
    assert extract_value("是139", []) == "139"
    assert extract_value("139", []) == "139"
    assert extract_value("手机号是139", ["手机号"]) == "139"
    assert extract_value("", []) is None


def test_locate_slot():
    aliases = {"receiver_name": ["姓名"], "receiver_phone": ["手机号", "电话"]}
    # 未提及字段名 → 用 fallback
    assert locate_slot("不对，是139", aliases, "receiver_phone") == "receiver_phone"
    # 提及字段名 → 命中对应槽位
    assert locate_slot("手机号改成139", aliases, "receiver_name") == "receiver_phone"


# —— 纠正：仅更新目标槽位（PRD 10.1.1 场景二）——
def test_correct_only_target_slot():
    ex = FlowExecutor({"modify_address": _address_flow()})
    _, results = _run_turns(ex, ["改地址", "张三", "13800001111", "不对，是13900002222"])
    slots = results[3]["slots"]
    assert slots["receiver_name"] == "张三"  # 未污染
    assert slots["receiver_phone"] == "13900002222"  # 已更新
    assert "已更正" in results[3]["response"]
    assert "请提供地址" in results[3]["response"]  # 继续问当前槽位


def test_correct_by_field_name():
    ex = FlowExecutor({"modify_address": _address_flow()})
    _, results = _run_turns(ex, ["改地址", "张三", "13800001111", "手机号改成13900002222"])
    slots = results[3]["slots"]
    assert slots["receiver_phone"] == "13900002222"
    assert slots["receiver_name"] == "张三"


# —— 跳过 / 取消 / 重新 ——
def test_skip_optional_slot():
    flow = Flow(id="f", name="f", triggers=["t"], steps=[
        FlowStep(id="s1", type="collect", slot="a", prompt="A", optional=True),
        FlowStep(id="s2", type="collect", slot="b", prompt="B"),
    ])
    ex = FlowExecutor({"f": flow})
    _, results = _run_turns(ex, ["t", "跳过", "值B"])
    assert results[1]["response"] == "B"  # 跳过 a，直接问 b
    assert "a" not in results[1]["slots"]


def test_skip_required_rejected():
    flow = Flow(id="f", name="f", triggers=["t"], steps=[
        FlowStep(id="s1", type="collect", slot="a", prompt="A"),
    ])
    ex = FlowExecutor({"f": flow})
    _, results = _run_turns(ex, ["t", "跳过"])
    assert "必填" in results[1]["response"]
    assert results[1]["slots"] == {}


def test_cancel_flow():
    flow = Flow(id="f", name="f", triggers=["t"], steps=[
        FlowStep(id="s1", type="collect", slot="a", prompt="A"),
    ])
    ex = FlowExecutor({"f": flow})
    _, results = _run_turns(ex, ["t", "取消"])
    assert "取消" in results[1]["response"]
    assert results[1]["active_flow"] is None
    assert results[1]["flow_stack"] == []


def test_rewind_recollect():
    flow = Flow(id="f", name="f", triggers=["t"], steps=[
        FlowStep(id="s1", type="collect", slot="a", prompt="A"),
        FlowStep(id="s2", type="collect", slot="b", prompt="B"),
    ])
    ex = FlowExecutor({"f": flow})
    state, results = _run_turns(ex, ["t", "值a", "重新"])
    assert results[2]["response"] == "A"  # 回到 a 重新收集
    assert state["flow_stack"][0]["slots"].get("a") is None  # a 已清空
