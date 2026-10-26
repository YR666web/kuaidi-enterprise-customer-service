"""平台 SQLAlchemy 模型：Tenant / User / AuditLog + 租户隔离 Mixin。"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantMixin:
    """租户隔离 Mixin：所有业务模型强制带 tenant_id。"""

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)


class Tenant(Base):
    """租户。"""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))


class User(Base):
    """用户（含角色）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    username: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))  # agent / operator / admin


class AuditLog(Base):
    """审计日志。"""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)  # login/config_change/data_export
    resource: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
