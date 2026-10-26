"""编排层节点实现：understand → execute → respond。

节点职责：
- understand：记录本轮用户消息 + 重置本轮临时状态 + 意图识别
- execute：  活跃流程优先 → workflow；否则走降级链（router.FallbackChain）
- respond：  组装最终回复 + 写入历史

降级链（route → execute → degrade → fallback + guard）由 router.FallbackChain 承载。
"""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agent import router
from app.agent.responder import CustomerServiceResponder
from app.agent.service import (
    AgentUnavailableError,
    run_readonly_agent,
    should_run_readonly_agent,
)
from app.agent.state import AgentState, Intent
from app.capabilities.graphrag import build_graphrag_service
from app.capabilities.rag import build_rag_service
from app.capabilities.rag.qa import LLMAnswerGenerator
from app.capabilities.workflow import build_workflow_capability
from app.core.config import settings
from app.llm import has_llm

# 意图路由（已配置 LLM 则用 DeepSeek，否则关键词 Mock）
INTENT_ROUTER = router.LLMIntentRouter() if has_llm() else router.KeywordIntentRouter()

# 能力实例采用懒加载：启动编排图不会立即加载向量模型或连接 Neo4j。
_rag_service = None
_graphrag_service = None
_customer_responder = CustomerServiceResponder()


def _rag(state: AgentState) -> dict[str, Any]:
    global _rag_service
    if _rag_service is None:
        _rag_service = build_rag_service(enable_rerank=False)
    question = state.get("user_input", "")
    tenant_id = state.get("tenant_id", "default")
    if state.get("stream_response") and isinstance(
        _rag_service.qa.generator, LLMAnswerGenerator
    ):
        contexts = _rag_service.qa.contexts(question, tenant_id=tenant_id)
        if contexts is None:
            return {"response": _rag_service.qa.no_answer_reply, "citations": []}
        citations = [f"{source.metadata.get('doc_id', source.id)}#{source.metadata.get('index', 0)}"
                     for source in contexts]
        return {
            "response": "",
            "citations": citations,
            "stream_plan": {
                "kind": "rag",
                "question": question,
                "passages": _rag_service.qa.generator.passages(contexts),
            },
        }
    answer = _rag_service.qa.answer(question, tenant_id=tenant_id)
    citations = [
        f"{source.doc_id}#{source.index}" for source in answer.sources
    ]
    return {"response": answer.text, "citations": citations}


def _graphrag(state: AgentState) -> dict[str, Any]:
    global _graphrag_service
    if _graphrag_service is None:
        _graphrag_service = build_graphrag_service()
    answer = _graphrag_service.ask(
        state.get("user_input", ""), user_id=state.get("user_id")
    )
    return {"response": answer.text, "citations": [answer.cypher] if answer.cypher else []}


CAPABILITIES: dict[str, Callable[[AgentState], dict[str, Any]]] = {
    "workflow": build_workflow_capability(),
    "rag": _rag,
    "graphrag": _graphrag,
}


# —— 能力 → CapabilityResult 适配（供降级链使用，call 时查 CAPABILITIES 以便测试注入）——
def _wrap_capability(name: str, *, success_check=None):
    def capability(query: str, context: dict) -> router.CapabilityResult:
        fn = CAPABILITIES.get(name)
        if fn is None:
            return router.CapabilityResult(success=False, error=f"未知能力: {name}")
        try:
            result = fn(context) or {}
            text = result.get("response", "")
            ok = success_check(text) if success_check else True
            return router.CapabilityResult(
                success=ok,
                text=text,
                citations=result.get("citations", []),
                state_updates=result if ok else {},
            )
        except Exception as exc:
            return router.CapabilityResult(success=False, error=str(exc))

    return capability


def _workflow_ok(text: str) -> bool:
    # workflow 未匹配到流程 → 视为"无结果"，触发降级
    return "未识别" not in text


_DEGRADATION_OBSERVER = router.DegradationObserver()
_FALLBACK_CHAIN = router.FallbackChain(
    {
        "workflow": _wrap_capability("workflow", success_check=_workflow_ok),
        "rag": _wrap_capability("rag"),
        "graphrag": _wrap_capability("graphrag"),
    },
    max_actions=settings.agent.max_actions,
    observer=_DEGRADATION_OBSERVER,
)


# —— 节点 ——
def understand_node(state: AgentState) -> dict[str, Any]:
    """入口节点：记录用户消息、重置本轮临时状态、识别意图。"""
    user_input = state.get("user_input", "")
    # 跟进问题必须继承上一轮上下文，不能被 LLM/关键词路由误判成欢迎语。
    previous = state.get("messages", [])
    previous_text = " ".join(str(getattr(m, "content", "")) for m in previous[-4:])
    skeptical_words = ("你怎么知道", "怎么知道", "随便编", "真的假的", "准确吗", "可靠吗")
    skeptical = any(word in user_input for word in skeptical_words)
    if skeptical and any(word in previous_text for word in ("物流单号", "运输中", "预计", "快递")):
        decision = router.IntentDecision(intent=Intent.RAG, confidence=0.95)
    else:
        decision = INTENT_ROUTER.route(user_input, previous_text)
    return {
        "messages": [HumanMessage(content=user_input)],
        "intent": decision.intent,
        "intent_confidence": decision.confidence,
        "response_tier": router.response_tier(user_input, decision.intent),
        "next_capability": None,
        "degradation_path": [],
        "tool_trace": [],
        "last_error": None,
        "action_count": 0,
        "response": "",
        "citations": [],
        "stream_plan": {},
    }


def execute_node(state: AgentState) -> dict[str, Any]:
    """执行节点：活跃流程优先 → workflow；否则走降级链。"""
    # 活跃流程优先：对话栈非空时，本轮输入属于流程内（槽位/中断）
    if state.get("flow_stack"):
        fn = CAPABILITIES.get("workflow")
        try:
            result = (fn(state) if fn else {}) or {}
            updates = {
                **result,
                "response": result.get("response", ""),
                "last_error": None,
                "tool_trace": [{"tool": "workflow", "status": "success"}],
            }
            # 已完成的业务动作交给客服模型基于真实工具结果流式解释；收集槽位时保留即时提示。
            if state.get("stream_response") and not result.get("flow_stack"):
                updates["stream_plan"] = {
                    "kind": "customer",
                    "verified_result": result.get("response", ""),
                }
                updates["response"] = ""
            return updates
        except Exception as exc:
            return {"response": router.FALLBACK_REPLY, "last_error": str(exc)}

    # 无活跃流程 → 降级链（route → execute → degrade → fallback）
    query = state.get("user_input", "")
    # 已包含物流单号的实时查询：在主 LangGraph 链路内使用 LLM
    # 自主选择只读工具。缺少单号时仍交给 Workflow 做多轮填槽。
    if state.get("intent") == Intent.WORKFLOW and should_run_readonly_agent(query):
        try:
            result = run_readonly_agent(query, state.get("tenant_id", "default"))
        except AgentUnavailableError:
            pass  # 未配置模型时回退到原有确定性 Workflow。
        else:
            return {
                "response": result.answer,
                "tool_trace": result.trace,
                "action_count": result.steps,
                "last_error": None if result.status == "completed" else result.status,
                "citations": [],
            }
    previous_text = " ".join(str(getattr(m, "content", "")) for m in state.get("messages", [])[-4:])
    skeptical_words = ("你怎么知道", "怎么知道", "随便编", "真的假的", "准确吗", "可靠吗")
    if any(word in query for word in skeptical_words) and "物流单号" in previous_text:
        return {
            "response": (
                "你说得对，我刚才把演示数据当成了真实物流结果。"
                "当前系统没有接入快递公司的实时查询接口，不能声称‘运输中’或‘预计送达’。"
                "请接入快递 100、顺丰等真实物流 API 后，我才能返回可核验的轨迹。"
            ),
            "tool_trace": [{"tool": "transparency_guard", "status": "success"}],
            "last_error": None,
            "citations": [],
        }
    intent = state.get("intent", Intent.FALLBACK)
    outcome = _FALLBACK_CHAIN.run(query, intent, state)
    return {
        "response": outcome.text,
        "degradation_path": outcome.degradation_path,
        "tool_trace": [
            {
                "tool": level,
                "status": "degraded" if level in outcome.degradation_path else "success",
            }
            for level in ([*outcome.degradation_path, outcome.level]
                          if outcome.level != "fallback" else outcome.degradation_path)
        ],
        "action_count": outcome.actions,
        "citations": [],
        "last_error": None,
        **outcome.state_updates,
    }


def respond_node(state: AgentState, config: RunnableConfig | None = None) -> dict[str, Any]:
    """响应节点：组装最终回复（空则兜底）+ 写入历史。"""
    response = state.get("response") or router.FALLBACK_REPLY
    stream_plan = state.get("stream_plan") or {}
    if stream_plan.get("kind") == "rag" and not state.get("stream_response"):
        generator = _rag_service.qa.generator if _rag_service is not None else None
        if isinstance(generator, LLMAnswerGenerator):
            response = "".join(generator.stream_generate(
                stream_plan["question"], stream_plan["passages"], config=config
            ))
    # 固定欢迎语/兜底以及已完成业务动作都由模型生成；业务事实仅作为受约束输入。
    elif (
        response in {router.CHITCHAT_REPLY, router.FALLBACK_REPLY}
        or stream_plan.get("kind") == "customer"
    ) and not state.get("stream_response"):
        generated = _customer_responder.reply(
            state.get("user_input", ""),
            state.get("messages", []),
            verified_result=stream_plan.get("verified_result", "无"),
            tier=state.get("response_tier", "fast"),
        )
        if generated:
            response = generated
    # 只有 SSE 请求才通过 stream() 产生事件；同步接口沿用 invoke()。
    if state.get("stream_response"):
        if stream_plan.get("kind") == "rag":
            generator = _rag_service.qa.generator if _rag_service is not None else None
            if isinstance(generator, LLMAnswerGenerator):
                response = "".join(generator.stream_generate(
                    stream_plan["question"], stream_plan["passages"], config=config
                ))
        elif (
            response in {router.CHITCHAT_REPLY, router.FALLBACK_REPLY}
            or stream_plan.get("kind") == "customer"
        ):
            chunks = _customer_responder.stream_reply(
                state.get("user_input", ""),
                state.get("messages", []),
                verified_result=stream_plan.get("verified_result", "无"),
                tier=state.get("response_tier", "fast"),
                config=config,
            )
            streamed = "".join(chunks)
            if streamed:
                response = streamed
    result = {
        "response": response,
        "citations": state.get("citations", []),
    }
    result["messages"] = [AIMessage(content=response)]
    return result
