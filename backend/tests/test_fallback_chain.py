"""降级链测试：意图路由、FallbackChain 降级顺序、guard、可观测。"""

from app.agent import router
from app.agent.state import Intent


# —— 意图路由 ——
def test_intent_router():
    d = router.KeywordIntentRouter().route("退换货政策是什么")
    assert d.intent == Intent.RAG
    assert 0.0 <= d.confidence <= 1.0


# —— 降级链 ——
def _ok(text="答案", score=1.0):
    return router.CapabilityResult(success=True, text=text, score=score)


def _fail(reason="失败"):
    return router.CapabilityResult(success=False, error=reason)


def _caps(results):
    return {level: (lambda q, c, r=res: r) for level, res in results.items()}


def test_fallback_chain_workflow_first():
    chain = router.FallbackChain(_caps({"workflow": _ok("流程办理中")}))
    out = chain.run("帮我退货", Intent.WORKFLOW)
    assert out.level == "workflow"
    assert out.text == "流程办理中"


def test_fallback_chain_degrades_to_next_level():
    chain = router.FallbackChain(_caps({
        "workflow": _fail("无流程匹配"),
        "rag": _ok("知识库答案"),
    }))
    out = chain.run("退换货政策", Intent.WORKFLOW)
    assert out.level == "rag"
    assert out.degradation_path == ["workflow"]
    assert out.reasons == ["无流程匹配"]


def test_fallback_chain_full_degrade_to_fallback():
    chain = router.FallbackChain(_caps({
        "workflow": _fail("a"),
        "rag": _fail("b"),
        "graphrag": _fail("c"),
    }))
    out = chain.run("q", Intent.WORKFLOW)
    assert out.level == "fallback"
    assert out.text == router.FALLBACK_REPLY
    assert out.degradation_path == ["workflow", "rag", "graphrag"]


def test_fallback_chain_starts_from_intent():
    # intent=rag → 从 rag 开始，跳过 workflow
    chain = router.FallbackChain(_caps({"rag": _ok("rag 答案")}))
    out = chain.run("政策", Intent.RAG)
    assert out.level == "rag"
    assert out.degradation_path == []


def test_fallback_chain_chitchat_direct():
    chain = router.FallbackChain({})
    out = chain.run("你好", Intent.CHITCHAT)
    assert out.level == "chitchat"
    assert out.text == router.CHITCHAT_REPLY


def test_fallback_chain_guard_max_actions():
    # max_actions=1 → 只执行一级即被 guard 截断 → 兜底
    chain = router.FallbackChain(
        _caps({"workflow": _fail(), "rag": _fail(), "graphrag": _fail()}),
        max_actions=1,
    )
    out = chain.run("q", Intent.WORKFLOW)
    assert out.level == "fallback"
    assert out.actions == 1


def test_fallback_chain_threshold():
    # 低于阈值的分数视为失败
    chain = router.FallbackChain(
        _caps({"workflow": _ok("低分", score=0.1), "rag": _ok("高分", score=0.9)}),
        score_threshold=0.5,
    )
    out = chain.run("q", Intent.WORKFLOW)
    assert out.level == "rag"


# —— 可观测 ——
def test_degradation_observer():
    observer = router.DegradationObserver()
    chain = router.FallbackChain(
        _caps({"workflow": _fail("无流程"), "rag": _fail("无结果"), "graphrag": _fail("无图")}),
        observer=observer,
    )
    chain.run("q", Intent.WORKFLOW)
    assert observer.count("workflow") == 1
    assert observer.count("rag") == 1
    assert observer.count("graphrag") == 1
    assert observer.count("fallback") == 1
    assert observer.count() == 4
