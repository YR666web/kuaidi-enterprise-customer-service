"""Workflow 能力测试：Flow 加载、对话栈、槽位填充、执行器、中断/恢复、端到端。"""

from app.agent.graph import build_graph
from app.capabilities.workflow.executor import FlowExecutor, evaluate_condition
from app.capabilities.workflow.flow import Flow, FlowStep, load_flows, match_flow
from app.capabilities.workflow.slot_filling import SlotDecision, decide, validate_value
from app.capabilities.workflow.stack import DialogueStack


# —— Flow 模型与 YAML 加载 ——
def _make_flow() -> Flow:
    return Flow(
        id="f1",
        name="测试流程",
        triggers=["测试"],
        steps=[
            FlowStep(id="s1", type="collect", slot="name", prompt="请提供姓名"),
            FlowStep(
                id="s2",
                type="collect",
                slot="phone",
                prompt="请提供手机号",
                validate="phone",
            ),
            FlowStep(id="s3", type="set_slot", slot="channel", value="app"),
            FlowStep(id="s4", type="condition", condition="channel == app", then="s5", else_="s5"),
            FlowStep(id="s5", type="action", action="submit"),
        ],
    )


def test_flow_model():
    flow = _make_flow()
    assert flow.step_by_id("s2").slot == "phone"
    assert flow.step_by_id("nope") is None
    assert flow.first_step().id == "s1"


def test_load_flows(tmp_path):
    (tmp_path / "a.yaml").write_text(
        "id: a\nname: A\ntriggers: [甲]\nsteps:\n  - id: s\n    type: action\n    action: x\n",
        encoding="utf-8",
    )
    flows = load_flows(str(tmp_path))
    assert "a" in flows
    assert flows["a"].steps[0].action == "x"


def test_match_flow():
    flows = {
        "a": Flow(id="a", name="A", triggers=["退货"], steps=[]),
        "b": Flow(id="b", name="B", triggers=["查快递"], steps=[]),
    }
    assert match_flow("我要退货", flows).id == "a"
    assert match_flow("帮我查快递", flows).id == "b"
    assert match_flow("你好", flows) is None


# —— 对话栈 ——
def test_dialogue_stack_push_pop():
    stack = DialogueStack()
    stack.push_flow("a")
    stack.push_flow("b")
    assert len(stack) == 2
    assert stack.top().flow_id == "b"
    assert stack.pop_flow().flow_id == "b"
    assert stack.top().flow_id == "a"


def test_dialogue_stack_pop_to_flow():
    stack = DialogueStack()
    for fid in ("a", "b", "c"):
        stack.push_flow(fid)
    assert stack.pop_to_flow("a") is True
    assert stack.top().flow_id == "a"
    assert len(stack) == 1
    assert stack.pop_to_flow("zzz") is False


def test_dialogue_stack_serialization():
    stack = DialogueStack()
    stack.push_flow("a").slots["x"] = 1
    stack.push_flow("b")
    restored = DialogueStack.from_list(stack.to_list())
    assert len(restored) == 2
    assert restored.top().flow_id == "b"
    assert restored.to_list()[0]["slots"] == {"x": 1}


# —— 槽位填充 ——
def test_validate_value():
    assert validate_value("13800001111", "phone") is True
    assert validate_value("123", "phone") is False
    assert validate_value("张三", "name") is True
    assert validate_value("张3", "name") is False
    assert validate_value("北京市朝阳区某街道", "address") is True
    assert validate_value("abc", "address") is False
    assert validate_value("随便", None) is True


def test_decide():
    assert decide("13800001111", "phone") == SlotDecision.ACCEPT
    assert decide("abc", "phone") == SlotDecision.INVALID
    assert decide("换一个", "phone") == SlotDecision.DRIFT
    assert decide("", "phone") == SlotDecision.INVALID


# —— 条件求值 ——
def test_evaluate_condition():
    slots = {"channel": "app", "amount": 100, "vip": True}
    assert evaluate_condition("channel == app", slots) is True
    assert evaluate_condition("channel != web", slots) is True
    assert evaluate_condition("amount >= 50", slots) is True
    assert evaluate_condition("amount > 500", slots) is False


# —— 执行器 ——
def _state(user_input, flow_stack=None, active_flow=None, slots=None):
    return {
        "user_input": user_input,
        "flow_stack": flow_stack or [],
        "active_flow": active_flow,
        "slots": slots or {},
    }


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


def test_fresh_flow_asks_first_slot():
    ex = FlowExecutor({"f1": _make_flow()})
    out = ex.handle(_state("测试"))
    assert "请提供姓名" in out["response"]
    assert out["active_flow"] == "f1"
    assert out["slots"] == {}
    assert len(out["flow_stack"]) == 1


def test_multi_turn_collection():
    ex = FlowExecutor({"f1": _make_flow()})
    _, results = _run_turns(ex, ["测试", "张三", "13800001111"])
    assert "请提供姓名" in results[0]["response"]
    assert "请提供手机号" in results[1]["response"]
    # 第三轮：填手机号 → set_slot → condition → action submit → 流程结束
    assert results[2]["active_flow"] is None
    assert results[2]["response"]


def test_invalid_reprompts():
    ex = FlowExecutor({"f1": _make_flow()})
    state, results = _run_turns(ex, ["测试", "张三", "badphone"])
    assert "格式有误" in results[2]["response"]
    assert state["flow_stack"][0]["current_step"] == "s2"


def test_drift_not_filled():
    ex = FlowExecutor({"f1": _make_flow()})
    state, results = _run_turns(ex, ["测试", "张三", "换一个"])
    assert state["flow_stack"][0]["slots"].get("phone") is None
    assert "请提供手机号" in results[2]["response"]


def test_interrupt_and_resume():
    flows = {
        "f1": Flow(id="f1", name="改地址", triggers=["改地址"], steps=[
            FlowStep(id="s1", type="collect", slot="name", prompt="姓名"),
            FlowStep(id="s2", type="action", action="submit"),
        ]),
        "f2": Flow(id="f2", name="查快递", triggers=["查快递"], steps=[
            FlowStep(id="t1", type="collect", slot="no", prompt="单号"),
            FlowStep(id="t2", type="action", action="query"),
        ]),
    }
    ex = FlowExecutor(flows)
    _, results = _run_turns(ex, ["改地址", "先帮我查快递", "SF123", "张三"])
    assert results[0]["active_flow"] == "f1"
    assert results[1]["active_flow"] == "f2"
    assert len(results[1]["flow_stack"]) == 2
    assert results[2]["active_flow"] == "f1"  # 子流程结束，弹栈恢复
    assert len(results[2]["flow_stack"]) == 1
    assert results[3]["active_flow"] is None  # 父流程也结束


# —— 端到端（经 agent + checkpoint）——
def test_workflow_via_agent_checkpoint():
    graph = build_graph()
    thread_id = "wf-sess"

    def turn(text):
        return graph.invoke(
            {"user_input": text, "session_id": thread_id},
            {"configurable": {"thread_id": thread_id}},
        )

    s1 = turn("改地址")
    assert "姓名" in s1["response"]
    s2 = turn("张三")
    assert "手机号" in s2["response"]
    s3 = turn("13800001111")
    assert "地址" in s3["response"]
    s4 = turn("北京市朝阳区建国路1号")
    assert s4["active_flow"] is None
    assert s4["flow_stack"] == []
