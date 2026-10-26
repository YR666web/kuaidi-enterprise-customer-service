"""意图漂移测试（PRD 10.1.1 场景一 + 新业务流程中断/恢复）。"""

from app.capabilities.workflow.executor import FlowExecutor
from app.capabilities.workflow.flow import Flow, FlowStep


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
                prompt="请提供手机号", validate="phone", aliases=["手机号"],
            ),
            FlowStep(
                id="ask_address", type="collect", slot="receiver_address",
                prompt="请提供地址", aliases=["地址"],
            ),
        ],
    )


def test_lightweight_question_insert():
    # PRD 10.1.1 场景一：办改地址中途问"发什么快递" → 插入处理，不改变流程栈
    ex = FlowExecutor({"modify_address": _address_flow()})
    _, results = _run_turns(
        ex, ["改地址", "张三", "13800001111", "你们发什么快递？明天能到吗？", "北京市朝阳区1号"]
    )
    # 漂移点（第 4 轮）：栈不变，回答完回到当前槽位
    assert results[3]["active_flow"] == "modify_address"
    assert len(results[3]["flow_stack"]) == 1
    assert "请提供地址" in results[3]["response"]
    # 已填槽位不被污染
    assert results[3]["slots"]["receiver_name"] == "张三"
    assert results[3]["slots"]["receiver_phone"] == "13800001111"
    # 第 5 轮：继续填地址，流程完成
    assert results[4]["active_flow"] is None


def test_new_flow_interrupt_during_collection():
    # 改地址流程中用户说"查快递"（新业务流程）→ 压栈中断
    flows = {
        "modify_address": Flow(id="modify_address", name="改地址", triggers=["改地址"], steps=[
            FlowStep(id="ask_name", type="collect", slot="name", prompt="姓名"),
        ]),
        "query_logistics": Flow(id="query_logistics", name="查快递", triggers=["查快递"], steps=[
            FlowStep(id="ask_no", type="collect", slot="no", prompt="单号"),
        ]),
    }
    ex = FlowExecutor(flows)
    _, results = _run_turns(ex, ["改地址", "查快递"])
    assert results[0]["active_flow"] == "modify_address"
    assert results[1]["active_flow"] == "query_logistics"
    assert len(results[1]["flow_stack"]) == 2


def test_interrupt_then_resume_parent_flow():
    # 中断后子流程结束 → 弹栈恢复父流程
    flows = {
        "modify_address": Flow(id="modify_address", name="改地址", triggers=["改地址"], steps=[
            FlowStep(id="ask_name", type="collect", slot="name", prompt="姓名"),
            FlowStep(id="submit", type="action", action="submit"),
        ]),
        "query_logistics": Flow(id="query_logistics", name="查快递", triggers=["查快递"], steps=[
            FlowStep(id="ask_no", type="collect", slot="no", prompt="单号"),
            FlowStep(id="query", type="action", action="query"),
        ]),
    }
    ex = FlowExecutor(flows)
    _, results = _run_turns(ex, ["改地址", "查快递", "SF123", "张三"])
    assert results[0]["active_flow"] == "modify_address"
    assert results[1]["active_flow"] == "query_logistics"
    assert len(results[1]["flow_stack"]) == 2
    assert results[2]["active_flow"] == "modify_address"  # 子流程结束，弹栈恢复
    assert len(results[2]["flow_stack"]) == 1
    assert results[3]["active_flow"] is None  # 父流程也完成
