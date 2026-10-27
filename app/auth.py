"""Optional Supabase sign-in and math-class storage."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger("mathly.auth")
TIMEOUT = 10
CACHE_TTL = 300
CLASSES_TTL = 60


class AuthUnavailable(RuntimeError):
    pass


class ClassConflict(ValueError):
    pass


class SupabaseAuth:
    def __init__(self, url: str, key: str, teachers: frozenset[str] = frozenset(), secret: str = "",
                 developers: frozenset[str] = frozenset()):
        self.url, self.key, self.secret = url.rstrip("/"), key, secret
        self.teachers, self.developers = teachers, developers
        self._users: dict[str, tuple[float, dict]] = {}
        self._classes: tuple[float, list[dict]] | None = None
        self._access: dict[str, tuple[float, dict | None]] = {}
        self._lock = threading.Lock()

    def user(self, token: str) -> dict | None:
        now = time.monotonic()
        with self._lock:
            cached = self._users.get(token)
        if cached and cached[0] > now:
            return cached[1]
        request = urllib.request.Request(self.url + "/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": self.key, "User-Agent": "mathly/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403):
                return None
            raise AuthUnavailable(f"supabase answered {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise AuthUnavailable(str(exc)) from exc
        if not data.get("id"):
            return None
        user = {"id": data["id"], "email": data.get("email", "")}
        with self._lock:
            self._users[token] = (now + CACHE_TTL, user)
        return user

    def _admin(self, path: str, method: str = "GET", body=None, prefer: str = "return=representation"):
        if not self.secret:
            raise AuthUnavailable("SUPABASE_SECRET_KEY is not set")
        request = urllib.request.Request(self.url + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.secret}", "apikey": self.secret,
                     "Content-Type": "application/json", "Prefer": prefer, "User-Agent": "mathly/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            if exc.code == 409:
                raise ClassConflict(detail) from exc
            raise AuthUnavailable(f"supabase answered {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise AuthUnavailable(str(exc)) from exc

    def classes(self, fresh: bool = False) -> list[dict]:
        now = time.monotonic()
        with self._lock:
            cached = self._classes
        if cached and cached[0] > now and not fresh:
            return cached[1]
        rows: list[dict] = []
        if self.secret:
            try:
                rows = self._admin("/rest/v1/classes?select=*&order=created_at.desc") or []
            except AuthUnavailable as exc:
                if "answered 404" not in str(exc):
                    raise
                log.warning("the classes table is missing; every account is allowed")
        # During the database migration, ignore rows belonging to a removed product.
        rows = [row for row in rows if not row.get("subject") or row.get("subject") == "מתמטיקה"]
        for row in rows:
            row["emails"] = [str(value).lower() for value in row.get("emails") or []]
            row["teachers"] = [str(value).lower() for value in row.get("teachers") or []]
            row["lessons"] = row.get("lessons") or []
            row["nicknames"] = row.get("nicknames") or {}
        with self._lock:
            self._classes = (now + CLASSES_TTL, rows)
        return rows

    def save_class(self, class_id: int | None, name: str, emails: list[str], nicknames: dict[str, str],
                   lessons: list[str], *, teachers: list[str] | None = None, **_ignored) -> None:
        body = {"name": name, "emails": emails, "nicknames": nicknames, "lessons": lessons,
                "teachers": list(teachers or [])}
        if class_id is None:
            self._admin("/rest/v1/classes", "POST", body)
        elif not self._admin(f"/rest/v1/classes?id=eq.{int(class_id)}", "PATCH", body):
            raise KeyError(class_id)
        self._classes = None

    def delete_class(self, class_id: int) -> None:
        self._admin(f"/rest/v1/classes?id=eq.{int(class_id)}", "DELETE")
        self._classes = None

    def access_for(self, user_id: str, fresh: bool = False) -> dict | None:
        if not self.secret:
            return None
        now = time.monotonic()
        with self._lock:
            cached = self._access.get(user_id)
        if cached and cached[0] > now and not fresh:
            return cached[1]
        try:
            rows = self._admin("/rest/v1/user_access?" + urllib.parse.urlencode(
                {"user_id": f"eq.{user_id}", "select": "user_id,email,roles,updated_at"}))
            value = rows[0] if rows else None
        except AuthUnavailable as exc:
            if "answered 404" not in str(exc):
                raise
            value = None
        with self._lock:
            self._access[user_id] = (now + CLASSES_TTL, value)
        return value


def load_auth() -> SupabaseAuth | None:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not url or not key:
        log.info("sign-in is disabled; the math path is public")
        return None
    emails = lambda name: frozenset(re.split(r"[\s,;]+", os.environ.get(name, "").strip().lower())) - {""}
    return SupabaseAuth(url, key, emails("TEACHER_EMAILS"), os.environ.get("SUPABASE_SECRET_KEY", "").strip(),
                        emails("DEVELOPER_EMAILS"))
