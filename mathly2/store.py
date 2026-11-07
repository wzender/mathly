"""Where classes and students are kept. Two stores with the same methods:
InMemoryStore (tests and local development, lost on restart) and SupabaseStore (PostgREST with the secret key)."""
from __future__ import annotations

import itertools
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TIMEOUT = 10


class StoreUnavailable(RuntimeError):
    """The database could not be reached or refused the request."""


class ClassExists(ValueError):
    """The teacher already has a class with this name."""


class MemberExists(ValueError):
    """The email already belongs to a class."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._classes: dict[int, dict] = {}
        self._members: dict[str, dict] = {}   # email -> row

    def create_class(self, teacher_email: str, name: str) -> dict:
        with self._lock:
            if any(c["teacher_email"] == teacher_email and c["name"].lower() == name.lower() for c in self._classes.values()):
                raise ClassExists(name)
            row = {"id": next(self._ids), "name": name, "teacher_email": teacher_email, "created_at": _now()}
            self._classes[row["id"]] = row
            return dict(row)

    def classes_of(self, teacher_email: str) -> list[dict]:
        with self._lock:
            rows = [c for c in self._classes.values() if c["teacher_email"] == teacher_email]
            return [{**c, "students": sum(1 for m in self._members.values() if m["class_id"] == c["id"])} for c in rows]

    def get_class(self, class_id: int) -> dict | None:
        with self._lock:
            row = self._classes.get(class_id)
            return dict(row) if row else None

    def members(self, class_id: int) -> list[dict]:
        with self._lock:
            rows = [m for m in self._members.values() if m["class_id"] == class_id]
            return [{"email": m["email"], "user_id": m["user_id"], "added_at": m["added_at"]}
                    for m in sorted(rows, key=lambda m: m["added_at"])]

    def membership(self, email: str) -> dict | None:
        with self._lock:
            row = self._members.get(email)
            if not row:
                return None
            return {**row, "class_name": self._classes[row["class_id"]]["name"]}

    def add_member(self, class_id: int, email: str) -> None:
        with self._lock:
            if email in self._members:
                raise MemberExists(email)
            self._members[email] = {"class_id": class_id, "email": email, "user_id": None, "added_at": _now()}

    def remove_member(self, class_id: int, email: str) -> bool:
        with self._lock:
            row = self._members.get(email)
            if not row or row["class_id"] != class_id:
                return False
            del self._members[email]
            return True

    def link_user(self, email: str, user_id: str) -> None:
        with self._lock:
            row = self._members.get(email)
            if row and not row["user_id"]:
                row["user_id"] = user_id


class SupabaseStore:
    def __init__(self, url: str, secret: str) -> None:
        self.url, self.secret = url.rstrip("/"), secret

    def _request(self, method: str, table: str, params: dict[str, str] | None = None, body: dict | None = None,
                 returning: bool = False):
        query = "&".join(f"{k}={urllib.parse.quote(v, safe='(),.*:')}" for k, v in (params or {}).items())
        headers = {"apikey": self.secret, "Authorization": f"Bearer {self.secret}", "User-Agent": "mathly2/1.0",
                   "Content-Type": "application/json"}
        if returning:
            headers["Prefer"] = "return=representation"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.url}/rest/v1/{table}" + (f"?{query}" if query else ""),
                                         data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                raise
            raise StoreUnavailable(f"supabase answered {exc.code} for {method} {table}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise StoreUnavailable(str(exc)) from exc
        return json.loads(raw) if raw else None

    @staticmethod
    def _eq(value) -> str:
        return f"eq.{value}"

    def create_class(self, teacher_email: str, name: str) -> dict:
        try:
            rows = self._request("POST", "m2_classes", body={"teacher_email": teacher_email, "name": name}, returning=True)
        except urllib.error.HTTPError as exc:
            raise ClassExists(name) from exc
        return rows[0]

    def classes_of(self, teacher_email: str) -> list[dict]:
        rows = self._request("GET", "m2_classes", {"teacher_email": self._eq(teacher_email),
                             "select": "id,name,teacher_email,created_at,m2_class_members(count)", "order": "created_at"})
        return [{**{k: r[k] for k in ("id", "name", "teacher_email", "created_at")},
                 "students": (r.get("m2_class_members") or [{"count": 0}])[0]["count"]} for r in rows]

    def get_class(self, class_id: int) -> dict | None:
        rows = self._request("GET", "m2_classes", {"id": self._eq(class_id), "select": "id,name,teacher_email,created_at"})
        return rows[0] if rows else None

    def members(self, class_id: int) -> list[dict]:
        return self._request("GET", "m2_class_members", {"class_id": self._eq(class_id),
                             "select": "email,user_id,added_at", "order": "added_at"})

    def membership(self, email: str) -> dict | None:
        rows = self._request("GET", "m2_class_members", {"email": self._eq(email),
                             "select": "class_id,email,user_id,added_at,m2_classes(name)"})
        if not rows:
            return None
        row = rows[0]
        return {**{k: row[k] for k in ("class_id", "email", "user_id", "added_at")}, "class_name": row["m2_classes"]["name"]}

    def add_member(self, class_id: int, email: str) -> None:
        try:
            self._request("POST", "m2_class_members", body={"class_id": class_id, "email": email})
        except urllib.error.HTTPError as exc:
            raise MemberExists(email) from exc

    def remove_member(self, class_id: int, email: str) -> bool:
        rows = self._request("DELETE", "m2_class_members", {"class_id": self._eq(class_id), "email": self._eq(email)},
                             returning=True)
        return bool(rows)

    def link_user(self, email: str, user_id: str) -> None:
        self._request("PATCH", "m2_class_members", {"email": self._eq(email), "user_id": "is.null"}, {"user_id": user_id})
