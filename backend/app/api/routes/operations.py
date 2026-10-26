"""客服工作台、流程配置与运营看板接口。"""

from pathlib import Path

import fastapi
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.platform.rbac import Permission, require_permission
from app.services.handoff import handoff_service
from app.services.sessions import session_service

router = APIRouter(tags=["operations"])
_chat_write = fastapi.Depends(require_permission(Permission.CHAT_WRITE))
_flow_config = fastapi.Depends(require_permission(Permission.FLOW_CONFIG))


class FeedbackRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    category: str = Field(default="general", max_length=64)
    comment: str = Field(default="", max_length=2_000)


@router.get("/sessions")
def list_sessions(tenant=_chat_write) -> list[dict]:
    return session_service.list(tenant.tenant_id)


@router.patch("/sessions/{session_id}")
def update_session(session_id: str, status: str, tenant=_chat_write) -> dict:
    result = session_service.update_status(session_id, status, tenant.tenant_id)
    if result is None:
        return {"ok": False, "detail": "会话不存在"}
    return result


@router.get("/handoffs")
def list_handoffs(tenant=_chat_write) -> list[dict]:
    return handoff_service.list_queue(tenant.tenant_id)


@router.post("/handoffs/{session_id}/accept")
def accept_handoff(session_id: str, tenant=_chat_write) -> dict:
    result = handoff_service.accept(session_id, tenant.tenant_id, tenant.user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="转人工任务不存在")
    return result


@router.post("/sessions/{session_id}/feedback")
def submit_feedback(session_id: str, req: FeedbackRequest, tenant=_chat_write) -> dict:
    return handoff_service.feedback(
        session_id, tenant.tenant_id, req.score, req.category, req.comment
    )


@router.get("/quality/summary")
def quality_summary(tenant=_flow_config) -> dict:
    return handoff_service.quality_summary(tenant.tenant_id)


@router.get("/flows")
def list_flows(_tenant=_flow_config) -> list[dict]:
    result = []
    directory = Path(settings.workflow.flows_dir)
    for path in sorted(directory.glob("*.y*ml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        result.append({
            "id": data.get("id", path.stem),
            "name": data.get("name", path.stem),
            "description": data.get("description", "声明式业务流程"),
            "steps": len(data.get("steps", [])),
            "updatedAt": int(path.stat().st_mtime * 1000),
        })
    return result


@router.get("/dashboard")
def dashboard() -> dict:
    from app.main import audit, metrics

    total = metrics.session_total._value.get()
    success = metrics.session_success._value.get()
    return {
        "sessions": int(total),
        "successRate": success / total if total else 1.0,
        "firstTokenLatency": metrics.first_token_latency_p95_ms(),
        "degradations": int(metrics.degradation._value.get()),
        "trend": metrics.trend(),
        "alerts": [a.__dict__ for a in metrics.check_alerts()],
        "auditCount": len(audit.events),
    }
