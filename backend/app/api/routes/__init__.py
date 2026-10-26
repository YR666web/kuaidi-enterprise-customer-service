"""路由聚合：所有子路由挂载到 api_router，统一由 main.py 加 /api/v1 前缀。"""

from fastapi import APIRouter

from app.api.routes import chat, evals, health, knowledge, operations

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(knowledge.router, tags=["knowledge"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(operations.router, tags=["operations"])
api_router.include_router(evals.router)
