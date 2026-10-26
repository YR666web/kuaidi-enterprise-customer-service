"""编排层测试：意图识别、降级链、checkpoint。"""

from app.agent import nodes, router
from app.agent.graph import build_graph
from app.agent.state import Intent


def _run(graph, text: str, thread_id: str = "t1") -> dict:
    """以给定文本启动一轮，返回最终状态。"""
    return graph.invoke(
        {"user_input": text, "session_id": thread_id},
        {"configurable": {"thread_id": thread_id}},
    )


def test_classify_intent() -> None:
    assert router.classify_intent("帮我退货")[0] == Intent.WORKFLOW
    assert router.classify_intent("退换货政策是什么")[0] == Intent.RAG
    assert router.classify_intent("这个品牌有哪些同类商品")[0] == Intent.GRAPHRAG
    assert router.classify_intent("你好")[0] == Intent.CHITCHAT
    assert router.classify_intent("zzzz")[0] == Intent.FALLBACK


def test_advisory_request_does_not_start_business_workflow() -> None:
    assert router.classify_intent("我想退货，想知道需要准备什么")[0] == Intent.FALLBACK


def test_response_tier_uses_reasoning_only_for_complex_questions() -> None:
    assert router.response_tier("你好", Intent.CHITCHAT) == "fast"
    assert router.response_tier("请对比两种退货方案", Intent.FALLBACK) == "reasoning"
    assert router.response_tier("商品关系是什么", Intent.GRAPHRAG) == "reasoning"


def test_llm_intent_router_falls_back_when_provider_fails(monkeypatch) -> None:
    class BrokenModel:
        def invoke(self, prompt):
            raise RuntimeError("provider unavailable")

    llm_router = router.LLMIntentRouter()
    llm_router._model = BrokenModel()
    decision = llm_router.route("我要退货")
    assert decision.intent == Intent.WORKFLOW


def test_workflow_happy_path() -> None:
    graph = build_graph()
    state = _run(graph, "我要退货")
    assert state["intent"] == Intent.WORKFLOW
    assert state["response"]
    assert state["last_error"] is None


def test_chitchat_uses_contextual_responder(monkeypatch) -> None:
    monkeypatch.setattr(
        nodes._customer_responder,
        "reply",
        lambda query, messages, **kwargs: "你好，有什么订单或售后问题？",
    )
    graph = build_graph()
    state = _run(graph, "你好")
    assert state["intent"] == Intent.CHITCHAT
    assert state["response"] == "你好，有什么订单或售后问题？"


def test_degradation_to_fallback(monkeypatch) -> None:
    # 三个能力全部失败 → 降级链耗尽 → 兜底
    def fail(state: dict) -> dict:
        raise RuntimeError("能力不可用")

    for capability in nodes.CAPABILITIES:
        monkeypatch.setitem(nodes.CAPABILITIES, capability, fail)
    monkeypatch.setattr(nodes._customer_responder, "reply", lambda query, messages, **kwargs: None)

    graph = build_graph()
    state = _run(graph, "我要退货")
    assert state["response"] == router.FALLBACK_REPLY
    assert state["degradation_path"] == ["workflow", "rag", "graphrag"]


def test_checkpoint_resume_and_time_travel() -> None:
    graph = build_graph()
    thread_id = "sess-1"
    _run(graph, "你好", thread_id=thread_id)
    second = _run(graph, "我要退货", thread_id=thread_id)

    # 历史累积：两轮共 2 条用户 + 2 条助手消息
    assert len(second["messages"]) >= 4
    assert second["messages"][0].type == "human"

    # 时间回溯：同 thread_id 下存在多个历史快照
    history = list(graph.get_state_history({"configurable": {"thread_id": thread_id}}))
    assert len(history) >= 2


def test_main_graph_routes_complete_logistics_query_to_tool_agent(monkeypatch) -> None:
    from app.agent.loop import LoopResult

    monkeypatch.setattr(
        nodes,
        "run_readonly_agent",
        lambda query, tenant_id: LoopResult(
            answer="经工具核验：暂无实时轨迹。",
            status="completed",
            steps=2,
            trace=[{"step": 1, "tool": "query_logistics", "status": "success"}],
        ),
    )
    graph = build_graph()
    state = _run(graph, "帮我查物流 SF12345678", thread_id="tool-agent-main")
    assert state["response"] == "经工具核验：暂无实时轨迹。"
    assert state["tool_trace"][0]["tool"] == "query_logistics"


def test_main_graph_keeps_incomplete_logistics_query_in_workflow(monkeypatch) -> None:
    monkeypatch.setattr(
        nodes,
        "run_readonly_agent",
        lambda *_args: (_ for _ in ()).throw(AssertionError("不应调用 AgentLoop")),
    )
    graph = build_graph()
    state = _run(graph, "帮我查物流", thread_id="workflow-main")
    assert "单号" in state["response"]
