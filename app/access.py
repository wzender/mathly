"""Mathly session roles and permissions."""
from __future__ import annotations

from .auth import SupabaseAuth

ROLES = frozenset({"student", "teacher", "admin", "developer"})
DEFAULT_ROLES = ("student",)
ROLE_PERMISSIONS = {
    "student": frozenset({"path.use"}),
    "teacher": frozenset({"path.use", "students.view"}),
    "admin": frozenset({"path.use", "students.view", "management.access", "classes.manage"}),
    "developer": frozenset({"*"}),
}


def resolve_access(store: SupabaseAuth, token: str, *, fresh_permissions: bool = False) -> dict | None:
    user = store.user(token)
    if user is None:
        return None
    email = user["email"].lower()
    classes = store.classes()
    mine = [row for row in classes if email in row.get("emails", ()) or email in row.get("teachers", ())]
    assigned = store.access_for(user["id"], fresh=fresh_permissions)
    roles = set((assigned or {}).get("roles") or DEFAULT_ROLES) & ROLES
    if email in store.teachers:
        roles.update({"teacher", "admin"})
    if email in store.developers:
        roles.add("developer")
    if classes and not mine and roles == {"student"}:
        return {**user, "denied": True, "permissions": []}
    permissions = set().union(*(ROLE_PERMISSIONS[role] for role in roles))
    return {**user, "token": token, "roles": sorted(roles), "permissions": sorted(permissions),
            "teacher": bool(roles & {"teacher", "admin", "developer"}), "classes": mine}


def has_permission(user: dict | None, permission: str) -> bool:
    permissions = set((user or {}).get("permissions", ()))
    return "*" in permissions or permission in permissions
