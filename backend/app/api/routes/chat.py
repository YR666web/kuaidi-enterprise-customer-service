"""对话 API：同步问答与 SSE 流式输出。"""

import json
from collections.abc import AsyncIterator
from time import perf_counter

import fastapi
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import build_graph
from app.platform.rbac import Permission, require_permission
from app.services.handoff import handoff_service
from app.services.sessions import session_service

router = APIRouter(prefix="/chat", tags=["chat"])
_chat_write = fastapi.Depends(require_permission(Permission.CHAT_WRITE))
graph = build_graph()


def _metrics():
    # 延迟导入，避免 app.main 挂载路由时形成循环导入。
    from app.main import metrics

    return metrics


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    session_id: str = Field(min_length=1, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    tenant_id: str = "default"


class HandoffRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(default="customer_requested", max_length=256)
    transcript: list[dict] = Field(default_factory=list, max_length=100)


def _thread_id(req: ChatRequest) -> str:
    """tenant 进入 checkpoint 键，避免不同租户复用同一 session_id。"""
    return f"{req.tenant_id}:{req.session_id}"


def _invoke(req: ChatRequest, *, stream_response: bool = False) -> dict:
    session_service.touch(req.session_id, req.message, req.user_id or "customer", req.tenant_id)
    return graph.invoke(
        {
            "user_input": req.message,
            "session_id": req.session_id,
            "tenant_id": req.tenant_id,
            "user_id": req.user_id,
            "stream_response": stream_response,
        },
        {"configurable": {"thread_id": _thread_id(req)}},
    )


@router.post("")
def chat(req: ChatRequest, _tenant=_chat_write) -> dict:
    """执行一轮对话，并返回 checkpoint 后的完整结果。"""
    req.tenant_id = _tenant.tenant_id
    started = perf_counter()
    state = _invoke(req)
    _metrics().record_session(success=True)
    _metrics().record_first_token_latency(perf_counter() - started)
    return {
        "session_id": req.session_id,
        "message": state.get("response", ""),
        "intent": state.get("intent"),
        "citations": state.get("citations", []),
        "degradation_path": state.get("degradation_path", []),
        "tool_trace": state.get("tool_trace", []),
    }


async def _sse_events(req: ChatRequest) -> AsyncIterator[str]:
    started = perf_counter()
    session_service.touch(req.session_id, req.message, req.user_id or "customer", req.tenant_id)
    graph_input = {
        "user_input": req.message,
        "session_id": req.session_id,
        "tenant_id": req.tenant_id,
        "user_id": req.user_id,
        "stream_response": True,
    }
    graph_config = {"configurable": {"thread_id": _thread_id(req)}}
    first_token_recorded = False
    emitted_tokens = False

    def event(delta: str) -> str:
        nonlocal first_token_recorded
        if not first_token_recorded:
            _metrics().record_first_token_latency(perf_counter() - started)
            first_token_recorded = True
        return f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"

    async for trace in graph.astream_events(graph_input, graph_config, version="v2"):
        event_name = trace.get("event")
        name = trace.get("name")
        if event_name == "on_chain_start" and name == "execute":
            payload = {"event": "tool", "status": "running"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        if event_name != "on_chat_model_stream":
            continue
        chunk = trace.get("data", {}).get("chunk")
        text = str(getattr(chunk, "content", "") or "")
        if text:
            emitted_tokens = True
            yield event(text)

    # 无需模型生成的槽位提示/工具结果直接发送真实最终状态；不存在逐字伪流式。
    state = graph.get_state(graph_config).values
    if not emitted_tokens:
        yield event(state.get("response", ""))
    _metrics().record_session(success=True)
    payload = {"done": True, "session_id": req.session_id, "intent": state.get("intent")}
    payload["tool_trace"] = state.get("tool_trace", [])
    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
def chat_stream(
    req: ChatRequest, _tenant=_chat_write
) -> StreamingResponse:
    """以 Server-Sent Events 返回逐字回复。"""
    req.tenant_id = _tenant.tenant_id
    return StreamingResponse(
        _sse_events(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/handoff")
def handoff(req: HandoffRequest, _tenant=_chat_write) -> dict:
    """客户显式转人工：创建排队任务并把最近对话交给坐席。"""
    return handoff_service.request(
        req.session_id, _tenant.tenant_id, reason=req.reason, transcript=req.transcript
    )
