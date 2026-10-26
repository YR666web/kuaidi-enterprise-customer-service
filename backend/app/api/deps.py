"""共享依赖注入（FastAPI Depends 复用）。

- get_db：SQLAlchemy 会话
- get_current_user / get_current_tenant：阶段 9 鉴权后补充
"""

from app.db.session import get_db

__all__ = ["get_db"]
