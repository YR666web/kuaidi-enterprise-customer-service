"""健康检查路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health")
def readiness(
    db: Session = Depends(get_db),
) -> dict:
    """就绪探针（readiness）：校验数据库连通性。"""
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "ok",
        "service": settings.app.name,
        "version": settings.app.version,
    }
