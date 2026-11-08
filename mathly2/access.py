"""Roles and permissions. Every route says which permission it needs, not which role: this file is the one place
that knows what each role may do. Roles are decided by the server on every request (never by the device)."""
from __future__ import annotations

import threading
import time
from typing import Callable, Iterable

from fastapi import Depends, HTTPException, Request

from . import reads
from .auth import current_user

ROLES = ("student", "teacher", "manager", "admin", "developer")
GRANTABLE = ("student", "teacher", "manager", "admin")   # roles an admin can give; developer comes only from the settings

# What each role may do. "*" (developer) is every permission.
PERMISSIONS: dict[str, frozenset[str]] = {
    "student": frozenset({"path.use"}),
    "teacher": frozenset({"path.use", "class.teach", "class.roster"}),
    "manager": frozenset({"classes.manage", "class.roster", "students.list"}),
    "admin": frozenset({"roles.manage"}),
    "developer": frozenset({"*"}),
}
CACHE_SECONDS = 30   # a role change shows within this many seconds (sooner on the server that made it)


def permissions_of(roles: Iterable[str]) -> frozenset[str]:
    return frozenset().union(*(PERMISSIONS.get(role, frozenset()) for role in roles))


def allowed(roles: Iterable[str], permission: str) -> bool:
    permissions = permissions_of(roles)
    return "*" in permissions or permission in permissions


def need(permission: str) -> Callable[..., dict]:
    """A route dependency: the caller is signed in and one of their roles has `permission`; else 403."""
    def dependency(user: dict = Depends(current_user)) -> dict:
        if not allowed(user["roles"], permission):
            raise HTTPException(403, "אין הרשאה לפעולה הזו")
        return user
    return dependency


def learner(request: Request, user: dict = Depends(need("path.use"))) -> dict:
    """Someone who may use the path: a teacher or developer, or a student who is in a class. A person whose
    only role is student and who is in no class is asked to talk to their teacher (403)."""
    if set(user["roles"]) == {"student"} and not reads.of(request).classes_of_student(user["email"]):
        raise HTTPException(403, "ask your teacher to add you to a class")
    return user


class RoleResolver:
    """The roles of an email, from the settings, the roles table and the classes (a class's teacher is a teacher,
    a class's student is a student). Cached per email for a few seconds so a page load costs a few store calls."""

    def __init__(self, settings, store, ttl: float = CACHE_SECONDS, clock: Callable[[], float] = time.monotonic) -> None:
        self.settings, self.store, self.ttl, self.clock = settings, store, ttl, clock
        self._cache: dict[str, tuple[float, frozenset[str]]] = {}
        self._lock = threading.Lock()

    def resolve(self, email: str, source=None) -> frozenset[str]:
        """`source` is the request's reads (so the classes read here are not read again by the handler); the store when None."""
        email = email.strip().lower()
        now = self.clock()
        with self._lock:
            cached = self._cache.get(email)
        if cached and cached[0] > now:
            return cached[1]
        source = source or self.store
        if hasattr(source, "prefetch"):                              # the three reads do not depend on each other: one wait
            source.prefetch(("roles_of", email), ("classes_taught", email), ("classes_of_student", email))
        roles = set(source.roles_of(email)) & set(GRANTABLE)        # a 'developer' row is ignored: it comes only from the settings
        if email in self.settings.developers:
            roles.add("developer")
        if email in self.settings.admins:
            roles.add("admin")
        if email in self.settings.teachers or source.classes_taught(email):
            roles.add("teacher")
        if source.classes_of_student(email):
            roles.add("student")
        if not roles:
            roles.add("student")
        found = frozenset(roles)
        with self._lock:
            self._cache[email] = (now + self.ttl, found)
        return found

    def forget(self, email: str | None = None) -> None:
        """Drop one email's cached roles, or all of them (after a class or role change)."""
        with self._lock:
            if email is None:
                self._cache.clear()
            else:
                self._cache.pop(email.strip().lower(), None)
