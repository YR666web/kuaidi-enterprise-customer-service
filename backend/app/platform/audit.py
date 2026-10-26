"""审计：登录、配置变更、数据导出写 audit_log。"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AuditEvent:
    """审计事件。"""

    action: str  # login / config_change / data_export
    tenant_id: str
    user_id: str
    resource: str = ""
    detail: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


class AuditService:
    """审计服务：记录审计事件（默认内存，可接 SQLAlchemy / 日志）。"""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(
        self, action: str, tenant_id: str, user_id: str, resource: str = "", detail: str = ""
    ) -> AuditEvent:
        event = AuditEvent(
            action=action, tenant_id=tenant_id, user_id=user_id,
            resource=resource, detail=detail,
        )
        self.events.append(event)
        return event

    def query(
        self, *, tenant_id: str | None = None, action: str | None = None
    ) -> list[AuditEvent]:
        events = self.events
        if tenant_id is not None:
            events = [e for e in events if e.tenant_id == tenant_id]
        if action is not None:
            events = [e for e in events if e.action == action]
        return events
