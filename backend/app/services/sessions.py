"""客服会话中心（进程内读写，接口保持可替换为 Redis/数据库）。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import time

from app.db.session import SessionLocal
from app.models.session import SupportSession


@dataclass
class SessionRecord:
    id: str
    customer_id: str = "customer"
    customer_name: str = "访客"
    status: str = "active"
    last_message: str = ""
    updated_at: int = field(default_factory=lambda: int(time() * 1000))
    unread: int = 0
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "customerId": self.customer_id,
            "customerName": self.customer_name,
            "avatar": self.customer_name[:1] or "客",
            "status": self.status,
            "lastMessage": self.last_message,
            "updatedAt": self.updated_at,
            "unread": self.unread,
            "tags": self.tags,
        }


class SessionService:
    def touch(
        self, session_id: str, message: str, customer_id: str = "customer",
        tenant_id: str = "default",
    ) -> SessionRecord:
        with SessionLocal() as db:
            row = db.query(SupportSession).filter(
                SupportSession.session_id == session_id,
                SupportSession.tenant_id == tenant_id,
            ).first()
            if row is None:
                row = SupportSession(
                    session_id=session_id, tenant_id=tenant_id, customer_id=customer_id
                )
                db.add(row)
            row.last_message = message
            row.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            db.refresh(row)
            return self._record(row)

    def list(self, tenant_id: str = "default") -> list[dict]:
        with SessionLocal() as db:
            rows = db.query(SupportSession).filter(
                SupportSession.tenant_id == tenant_id
            ).order_by(SupportSession.updated_at.desc()).all()
            return [self._record(row).as_dict() for row in rows]

    def update_status(
        self, session_id: str, status: str, tenant_id: str = "default"
    ) -> dict | None:
        with SessionLocal() as db:
            row = db.query(SupportSession).filter(
                SupportSession.session_id == session_id,
                SupportSession.tenant_id == tenant_id,
            ).first()
            if row is None:
                return None
            row.status = status
            row.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            db.refresh(row)
            return self._record(row).as_dict()

    @staticmethod
    def _record(row: SupportSession) -> SessionRecord:
        return SessionRecord(
            id=row.session_id,
            customer_id=row.customer_id,
            status=row.status,
            last_message=row.last_message,
            updated_at=int(row.updated_at.timestamp() * 1000),
        )


session_service = SessionService()
