"""Roles of accounts: an admin gives and takes away student, teacher, manager and admin. The developer role comes only
from the app's settings. Roles belong to an email, so one can be given before the person has ever signed in."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from .access import GRANTABLE, need
from .auth import EMAIL

router = APIRouter(prefix="/api/accounts")


def settings_roles(settings, email: str) -> list[str]:
    found = []
    if email in settings.developers:
        found.append("developer")
    if email in settings.admins:
        found.append("admin")
    if email in settings.teachers:
        found.append("teacher")
    return found


def checked(email: str, role: str) -> tuple[str, str]:
    email = email.strip().lower()
    if not EMAIL.match(email) or len(email) > 254:
        raise HTTPException(422, "כתובת המייל לא נראית תקינה")
    if role not in GRANTABLE:
        raise HTTPException(422, "אפשר לתת רק את התפקידים תלמיד, מורה, מנהל כיתות ומנהל הרשאות")
    return email, role


@router.get("")
def list_accounts(request: Request, user: dict = Depends(need("roles.manage"))) -> list[dict]:
    """Every email the app knows, with the roles given here and the ones the app's settings give."""
    settings = request.app.state.settings
    seen = {a["email"]: a for a in request.app.state.store.accounts()}
    for email in settings.developers | settings.admins | settings.teachers:
        seen.setdefault(email, {"email": email, "roles": []})
    return [{**a, "from_settings": settings_roles(settings, a["email"])} for _, a in sorted(seen.items())]


@router.post("/{email}/roles/{role}", status_code=204)
def give_role(email: str, role: str, request: Request, user: dict = Depends(need("roles.manage"))) -> None:
    email, role = checked(email, role)
    request.app.state.store.give_role(email, role, user["email"])
    request.app.state.roles.forget(email)


@router.delete("/{email}/roles/{role}", status_code=204)
def take_role(email: str, role: str, request: Request, user: dict = Depends(need("roles.manage"))) -> None:
    email, role = checked(email, role)
    result = request.app.state.store.take_role(email, role, len(request.app.state.settings.admins))
    if result == "last_admin":
        raise HTTPException(409, "אי אפשר להסיר את מנהל ההרשאות האחרון")
    if result == "absent":
        raise HTTPException(404, "לחשבון הזה אין את התפקיד")
    request.app.state.roles.forget(email)
