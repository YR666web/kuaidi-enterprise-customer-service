"""FastAPI 应用入口。

分层：接入层（本文件）→ api 路由 → 编排层/能力层。
启动（需在 backend/ 目录下）：`uv run python -m uvicorn app.main:app --reload`
"""

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest

from app.api.routes import api_router
from app.core.config import settings
from app.platform.audit import AuditService
from app.platform.monitoring import MetricsCollector
from app.platform.ratelimit import build_rate_limiter
from app.platform.tenant import JWTTokenParser, TenantMiddleware

metrics = MetricsCollector(
    error_rate_threshold=settings.platform.error_rate_threshold,
    latency_threshold_ms=settings.platform.latency_threshold_ms,
    degradation_threshold=settings.platform.degradation_threshold,
)
audit = AuditService()
rate_limiter = build_rate_limiter(settings.platform, settings.redis)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（知识库文档元信息等）
    from app.db.base import Base
    from app.db.session import engine
    from app.models.business import OrderRecord, ReturnRequestRecord  # noqa: F401
    from app.models.knowledge import (  # noqa: F401
        KnowledgeDocument,
        KnowledgeDocumentTenant,
        KnowledgeDocumentVersion,
    )
    from app.models.session import HandoffRecord, QualityFeedback, SupportSession  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if settings.agent.checkpoint_backend == "redis":
        # RedisSearch 索引初始化失败应阻止生产服务启动，而不是悄悄退回内存。
        from app.api.routes.chat import graph

        graph.checkpointer.setup()
    try:
        yield
    finally:
        if settings.agent.checkpoint_backend == "redis":
            client = getattr(graph.checkpointer, "_redis", None)
            if client is not None:
                client.close()
        limiter_client = getattr(rate_limiter, "redis", None)
        if limiter_client is not None:
            limiter_client.close()


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TenantMiddleware,
    parser=JWTTokenParser(settings.platform.jwt_secret, settings.platform.jwt_algorithm),
    exempt_paths=frozenset({
        "/health", "/api/v1/health", "/docs", "/redoc", "/openapi.json", "/metrics",
    }),
)

# 业务路由统一挂载到 /api/v1 前缀
app.include_router(api_router, prefix=settings.app.api_prefix)


@app.middleware("http")
async def observe_request(request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    if request.url.path.startswith("/api/"):
        tenant = getattr(request.state, "tenant", None)
        key = tenant.tenant_id if tenant else (request.client.host if request.client else "unknown")
        if not rate_limiter.allow(key):
            return JSONResponse(
                {"detail": "请求过于频繁，请稍后重试", "request_id": request_id},
                status_code=429,
                headers={"Retry-After": "60", "X-Request-ID": request_id},
            )
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        metrics.record_session(success=False)
        raise


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(metrics.registry).decode("utf-8"))


@app.get("/health", tags=["system"])
def health() -> dict:
    """存活探针（liveness）：不依赖任何中间件，仅校验进程可用。"""
    return {
        "status": "ok",
        "service": settings.app.name,
        "version": settings.app.version,
    }
