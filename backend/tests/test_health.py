"""健康检查最小冒烟测试。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_liveness() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
