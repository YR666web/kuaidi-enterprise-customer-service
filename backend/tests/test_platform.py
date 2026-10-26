"""平台能力测试：多租户、RBAC、监控告警、审计。"""

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.platform.audit import AuditService
from app.platform.monitoring import MetricsCollector
from app.platform.rbac import Permission, Role, has_permission, require_permission
from app.platform.tenant import (
    JWTTokenParser,
    MockTokenParser,
    TenantMiddleware,
    TokenPayload,
    enforce_tenant,
)


def test_production_rejects_default_security_backends():
    from pydantic import ValidationError

    from app.core.config import Settings

    try:
        Settings(app={"environment": "production"})
    except ValidationError as exc:
        assert "PLATFORM__JWT_SECRET" in str(exc)
    else:
        raise AssertionError("生产环不应接受默认密钥")


def test_production_accepts_redis_and_strong_secret():
    from app.core.config import Settings

    configured = Settings(
        app={"environment": "production"},
        agent={"checkpoint_backend": "redis"},
        platform={
            "jwt_secret": "a-strong-production-secret-with-32-chars",
            "rate_limit_backend": "redis",
        },
    )
    assert configured.platform.rate_limit_backend == "redis"


# —— JWT 解析 ——
def test_jwt_parse():
    import jwt

    secret = "a" * 32  # 满足 HMAC 最小密钥长度，避免警告
    parser = JWTTokenParser(secret)
    token = jwt.encode(
        {"sub": "u1", "tenant_id": "t1", "roles": ["agent"]}, secret, algorithm="HS256"
    )
    payload = parser.parse(token)
    assert payload.user_id == "u1"
    assert payload.tenant_id == "t1"
    assert payload.roles == ["agent"]


# —— 多租户中间件 ——
def test_tenant_middleware_sets_context():
    parser = MockTokenParser(TokenPayload(user_id="u1", tenant_id="t1", roles=["agent"]))

    def endpoint(request):
        tenant = getattr(request.state, "tenant", None)
        return JSONResponse({"tenant_id": tenant.tenant_id if tenant else None})

    app = Starlette(routes=[Route("/x", endpoint)])
    app.add_middleware(TenantMiddleware, parser=parser)

    resp = TestClient(app).get("/x", headers={"Authorization": "Bearer abc"})
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "t1"


def test_tenant_middleware_401_without_token():
    app = Starlette(routes=[Route("/x", lambda r: JSONResponse({"ok": True}))])
    app.add_middleware(TenantMiddleware, parser=MockTokenParser())

    resp = TestClient(app).get("/x")
    assert resp.status_code == 401


def test_enforce_tenant_rejects_cross_tenant():
    tenant = TokenPayload(user_id="u1", tenant_id="t1", roles=["agent"])
    enforce_tenant(tenant, "t1")  # 同租户，通过
    with pytest.raises(HTTPException) as exc:
        enforce_tenant(tenant, "t2")  # 跨租户，拒绝
    assert exc.value.status_code == 403


# —— RBAC ——
def test_has_permission():
    assert has_permission(Role.AGENT, Permission.CHAT_WRITE) is True
    assert has_permission(Role.AGENT, Permission.DATA_EXPORT) is False
    assert has_permission(Role.OPERATOR, Permission.DATA_EXPORT) is True
    assert has_permission(Role.ADMIN, Permission.TENANT_MANAGE) is True
    assert has_permission("unknown", Permission.CHAT_WRITE) is False


_EXPORT_DEP = require_permission(Permission.DATA_EXPORT)


def _app_with_role(role: str) -> FastAPI:
    parser = MockTokenParser(TokenPayload(user_id="u1", tenant_id="t1", roles=[role]))
    app = FastAPI()
    app.add_middleware(TenantMiddleware, parser=parser)

    @app.get("/export")
    def export(tenant=Depends(_EXPORT_DEP)):
        return {"tenant_id": tenant.tenant_id}

    return app


def test_require_permission_forbidden():
    resp = TestClient(_app_with_role("agent")).get(
        "/export", headers={"Authorization": "Bearer x"}
    )
    assert resp.status_code == 403  # 坐席无 data:export


def test_require_permission_allowed():
    resp = TestClient(_app_with_role("operator")).get(
        "/export", headers={"Authorization": "Bearer x"}
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "t1"


# —— 监控 ——
def test_metrics_and_alerts():
    m = MetricsCollector(
        error_rate_threshold=0.5, latency_threshold_ms=1000, degradation_threshold=2
    )
    m.record_session(success=False)
    m.record_session(success=False)
    m.record_session(success=True)
    assert m.success_rate() == 1 / 3
    m.record_latency(2.0)  # 2000ms > 1000ms
    assert m.first_token_latency_p95_ms() >= 2000
    m.record_degradation()
    m.record_degradation()
    m.record_degradation()  # 3 > 2
    names = {a.name for a in m.check_alerts()}
    assert "error_rate" in names
    assert "latency" in names
    assert "degradation" in names


# —— 审计 ——
def test_audit_record_and_query():
    svc = AuditService()
    svc.record("login", "t1", "u1")
    svc.record("config_change", "t1", "u2", resource="flow", detail="改流程")
    svc.record("data_export", "t2", "u1")
    assert len(svc.query(tenant_id="t1")) == 2
    assert len(svc.query(action="data_export")) == 1
    assert svc.query(tenant_id="t1", action="login")[0].user_id == "u1"
