"""SQLAlchemy 引擎与会话管理。

引擎创建是惰性的（不建立连接），因此即使中间件未启动，应用也能正常导入。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database.url,
    pool_pre_ping=True,
    echo=settings.database.echo,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
