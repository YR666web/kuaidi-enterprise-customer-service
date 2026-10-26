"""RBAC：角色（坐席/运营/管理员）与权限，接口级校验。"""

from enum import StrEnum

from fastapi import Depends, HTTPException

from app.platform.tenant import TokenPayload, get_current_tenant


class Role(StrEnum):
    AGENT = "agent"        # 坐席
    OPERATOR = "operator"  # 运营
    ADMIN = "admin"        # 管理员


class Permission(StrEnum):
    CHAT_WRITE = "chat:write"
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_WRITE = "knowledge:write"
    FLOW_CONFIG = "flow:config"
    DATA_EXPORT = "data:export"
    AUDIT_READ = "audit:read"
    TENANT_MANAGE = "tenant:manage"
    ROLE_MANAGE = "role:manage"
    EVAL_RUN = "eval:run"


# 角色 → 权限
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.AGENT: frozenset({Permission.CHAT_WRITE, Permission.KNOWLEDGE_READ}),
    Role.OPERATOR: frozenset({
        Permission.CHAT_WRITE,
        Permission.KNOWLEDGE_READ,
        Permission.KNOWLEDGE_WRITE,
        Permission.FLOW_CONFIG,
        Permission.DATA_EXPORT,
    }),
    Role.ADMIN: frozenset(Permission),
}


def has_permission(role: str, permission: Permission) -> bool:
    """判断角色是否拥有权限。"""
    try:
        r = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(r, frozenset())


def require_permission(permission: Permission):
    """FastAPI 依赖：校验当前用户任一角色拥有指定权限。"""

    def dependency(tenant: TokenPayload = Depends(get_current_tenant)):
        if not any(has_permission(role, permission) for role in tenant.roles):
            raise HTTPException(status_code=403, detail=f"缺少权限 {permission.value}")
        return tenant

    return dependency
