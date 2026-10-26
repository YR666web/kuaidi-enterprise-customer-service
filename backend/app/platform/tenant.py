"""多租户：token 解析 tenant_id、租户上下文、中间件、租户过滤。"""

from dataclasses import dataclass, field
from typing import Protocol

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass
class TokenPayload:
    """JWT 载荷。"""

    user_id: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)


class TokenParser(Protocol):
    """token 解析接口（可插拔：JWT / Mock）。"""

    def parse(self, token: str) -> TokenPayload: ...


class JWTTokenParser:
    """JWT 解析（懒加载 pyjwt）。"""

    def __init__(self, secret: str, algorithm: str = "HS256") -> None:
        self.secret = secret
        self.algorithm = algorithm

    def parse(self, token: str) -> TokenPayload:
        import jwt

        payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        return TokenPayload(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            roles=payload.get("roles", []),
        )


class MockTokenParser:
    """Mock 解析（测试用）：忽略 token，返回固定载荷。"""

    def __init__(self, payload: TokenPayload | None = None) -> None:
        self.payload = payload or TokenPayload(user_id="u1", tenant_id="t1", roles=["agent"])

    def parse(self, token: str) -> TokenPayload:
        return self.payload


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else None


class TenantMiddleware(BaseHTTPMiddleware):
    """中间件：从 Authorization 头解析 token，设置租户上下文；无效则 401。"""

    def __init__(
        self, app, parser: TokenParser, *, exempt_paths: frozenset[str] = frozenset()
    ) -> None:
        super().__init__(app)
        self.parser = parser
        self.exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next):
        request.state.tenant = None
        if request.url.path not in self.exempt_paths:
            token = _extract_bearer(request)
            try:
                request.state.tenant = self.parser.parse(token) if token else None
            except Exception:
                request.state.tenant = None
            if request.state.tenant is None:
                return JSONResponse({"detail": "未认证或无效 token"}, status_code=401)
        return await call_next(request)


def get_current_tenant(request: Request) -> TokenPayload:
    """FastAPI 依赖：获取当前租户上下文，未认证抛 401。"""
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(status_code=401, detail="未认证")
    return tenant


def enforce_tenant(tenant: TokenPayload, requested_tenant_id: str) -> None:
    """租户隔离：跨租户访问拒绝（403）。"""
    if tenant.tenant_id != requested_tenant_id:
        raise HTTPException(status_code=403, detail="跨租户访问被拒绝")


def tenant_filter(query, model, tenant_id: str):
    """SQLAlchemy 查询强制带 tenant_id 过滤。"""
    return query.filter(model.tenant_id == tenant_id)
