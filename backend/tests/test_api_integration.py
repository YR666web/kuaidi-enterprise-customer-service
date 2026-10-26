"""HTTP 集成与并发冒烟测试。"""

from concurrent.futures import ThreadPoolExecutor

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _headers(
    user_id: str = "u-test", roles: list[str] | None = None, tenant_id: str = "tenant-test"
) -> dict[str, str]:
    token = jwt.encode(
        {"sub": user_id, "tenant_id": tenant_id, "roles": roles or ["agent"]},
        settings.platform.jwt_secret,
        algorithm=settings.platform.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def test_chat_checkpoint_and_operations_endpoints():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            headers=_headers(),
            json={"session_id": "integration-1", "message": "你好"},
        )
        assert response.status_code == 200
        assert response.json()["message"]
        assert client.get("/api/v1/flows", headers=_headers(roles=["operator"])).status_code == 200
        sessions = client.get("/api/v1/sessions", headers=_headers())
        assert sessions.status_code == 200
        assert any(item["id"] == "integration-1" for item in sessions.json())
        assert client.patch(
            "/api/v1/sessions/integration-1?status=ended", headers=_headers()
        ).status_code == 200
        assert client.get("/api/v1/dashboard", headers=_headers()).status_code == 200


def test_chat_concurrent_sessions():
    def call(index: int) -> int:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat",
                headers=_headers(f"u-{index}"),
                json={"session_id": f"concurrent-{index}", "message": "你好"},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(call, range(4)))
    assert statuses == [200, 200, 200, 200]


def test_session_update_rejects_other_tenant():
    with TestClient(app) as client:
        session_id = "tenant-isolation-session"
        assert client.post(
            "/api/v1/chat",
            headers=_headers(tenant_id="tenant-a"),
            json={"session_id": session_id, "message": "你好"},
        ).status_code == 200
        response = client.patch(
            f"/api/v1/sessions/{session_id}?status=ended",
            headers=_headers(tenant_id="tenant-b"),
        )
        assert response.json()["ok"] is False


def test_eval_report_requires_admin_and_returns_results():
    with TestClient(app) as client:
        assert client.get("/api/v1/evals/report", headers=_headers()).status_code == 403
        response = client.post("/api/v1/evals/run", headers=_headers(roles=["admin"]))
        assert response.status_code == 200
        assert response.json()["accuracy"] == 1.0
        badcases = client.get("/api/v1/evals/badcases", headers=_headers(roles=["admin"]))
        assert badcases.status_code == 200
        assert badcases.json()["total"] >= 5


def test_handoff_preserves_context_and_quality_is_tenant_scoped():
    with TestClient(app) as client:
        headers = _headers(roles=["operator"], tenant_id="handoff-a")
        response = client.post(
            "/api/v1/chat/handoff",
            headers=headers,
            json={
                "session_id": "handoff-1",
                "reason": "customer_requested",
                "transcript": [
                    {"role": "user", "content": "我要退货"},
                    {"role": "assistant", "content": "请提供订单号"},
                ],
            },
        )
        assert response.status_code == 200
        assert "我要退货" in response.json()["summary"]
        assert client.get("/api/v1/handoffs", headers=headers).json()[0]["sessionId"] == "handoff-1"
        assert client.post("/api/v1/handoffs/handoff-1/accept", headers=headers).status_code == 200
        assert client.post(
            "/api/v1/sessions/handoff-1/feedback",
            headers=headers,
            json={"score": 2, "category": "answer_quality", "comment": "不够准确"},
        ).status_code == 200
        summary = client.get("/api/v1/quality/summary", headers=headers)
        assert summary.status_code == 200
        assert summary.json()["lowScoreCount"] >= 1
        other_tenant = _headers(roles=["operator"], tenant_id="handoff-b")
        assert client.get("/api/v1/handoffs", headers=other_tenant).json() == []
