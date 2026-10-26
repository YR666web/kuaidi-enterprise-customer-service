"""业务数据仓储（当前为可替换的内存实现）。"""

from app.repositories.business import BusinessRepositories, build_action_handler

__all__ = ["BusinessRepositories", "build_action_handler"]
