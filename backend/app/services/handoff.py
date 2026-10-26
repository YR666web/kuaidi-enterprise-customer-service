"""人工接管与会话质检服务。"""

import json
from datetime import UTC

from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.session import HandoffRecord, QualityFeedback
from app.services.sessions import session_service


class HandoffService:
    def request(
        self, session_id: str, tenant_id: str, *, reason: str, transcript: list[dict]
    ) -> dict:
        """创建排队任务，摘要与原始对话均与租户绑定。"""
        summary = self._summary(transcript)
        # 即使客户一打开页面就转人工，也创建会话，使工作台能立即看到它。
        session_service.touch(session_id, summary or "请求人工客服", tenant_id=tenant_id)
        with SessionLocal() as db:
            row = HandoffRecord(
                session_id=session_id,
                tenant_id=tenant_id,
                reason=reason or "customer_requested",
                summary=summary,
                transcript=json.dumps(transcript, ensure_ascii=False),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        session_service.update_status(session_id, "queued", tenant_id)
        return self._as_dict(row)

    def accept(self, session_id: str, tenant_id: str, agent_id: str) -> dict | None:
        with SessionLocal() as db:
            row = self._latest(db, session_id, tenant_id)
            if row is None:
                return None
            row.status = "active"
            row.accepted_by = agent_id
            db.commit()
            db.refresh(row)
            result = self._as_dict(row)
        session_service.update_status(session_id, "active", tenant_id)
        return result

    def list_queue(self, tenant_id: str) -> list[dict]:
        with SessionLocal() as db:
            rows = db.query(HandoffRecord).filter(
                HandoffRecord.tenant_id == tenant_id, HandoffRecord.status.in_(("queued", "active"))
            ).order_by(HandoffRecord.created_at.desc()).all()
            return [self._as_dict(row) for row in rows]

    def feedback(
        self, session_id: str, tenant_id: str, score: int, category: str, comment: str
    ) -> dict:
        with SessionLocal() as db:
            row = QualityFeedback(
                session_id=session_id, tenant_id=tenant_id, score=score,
                category=category, comment=comment,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._feedback_dict(row)

    def quality_summary(self, tenant_id: str) -> dict:
        with SessionLocal() as db:
            count, average = db.query(
                func.count(QualityFeedback.id), func.avg(QualityFeedback.score)
            ).filter(QualityFeedback.tenant_id == tenant_id).one()
            low = db.query(func.count(QualityFeedback.id)).filter(
                QualityFeedback.tenant_id == tenant_id, QualityFeedback.score <= 2
            ).scalar() or 0
        return {
            "feedbackCount": count,
            "averageScore": round(float(average), 2) if average is not None else None,
            "lowScoreCount": low,
        }

    @staticmethod
    def _latest(db, session_id: str, tenant_id: str) -> HandoffRecord | None:
        return db.query(HandoffRecord).filter(
            HandoffRecord.session_id == session_id, HandoffRecord.tenant_id == tenant_id
        ).order_by(HandoffRecord.created_at.desc()).first()

    @staticmethod
    def _summary(transcript: list[dict]) -> str:
        recent = transcript[-6:]
        lines = [
            f"{'客户' if item.get('role') == 'user' else '客服'}：{item.get('content', '')}"
            for item in recent
        ]
        return "\n".join(lines)[:2_000]

    @staticmethod
    def _as_dict(row: HandoffRecord) -> dict:
        return {
            "id": row.id, "sessionId": row.session_id, "reason": row.reason, "summary": row.summary,
            "transcript": json.loads(row.transcript), "status": row.status,
            "acceptedBy": row.accepted_by,
            "createdAt": int(row.created_at.replace(tzinfo=UTC).timestamp() * 1000),
        }

    @staticmethod
    def _feedback_dict(row: QualityFeedback) -> dict:
        return {
            "id": row.id,
            "sessionId": row.session_id,
            "score": row.score,
            "category": row.category,
            "comment": row.comment,
        }


handoff_service = HandoffService()
