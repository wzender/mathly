"""Who is calling. The browser signs in with Google through Supabase and sends its access token;
the server asks Supabase who the token belongs to. Teachers are the emails in TEACHER_EMAILS; everyone else is a student."""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
import uuid

from fastapi import Depends, HTTPException, Request

TIMEOUT = 10
CACHE_SECONDS = 300
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


class AuthUnavailable(RuntimeError):
    """Supabase could not be reached."""


class SupabaseAuthenticator:
    def __init__(self, url: str, key: str) -> None:
        self.url, self.key = url.rstrip("/"), key
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def user(self, token: str) -> dict | None:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(token)
        if cached and cached[0] > now:
            return cached[1]
        request = urllib.request.Request(self.url + "/auth/v1/user",
                                         headers={"Authorization": f"Bearer {token}", "apikey": self.key, "User-Agent": "mathly2/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403):
                return None
            raise AuthUnavailable(f"supabase answered {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise AuthUnavailable(str(exc)) from exc
        email = str(data.get("email") or "").strip().lower()
        # An email nobody confirmed could belong to someone else: never trust it, least of all for teacher rights.
        if not data.get("id") or not email or not (data.get("email_confirmed_at") or data.get("confirmed_at")):
            return None
        user = {"id": data["id"], "email": email}
        with self._lock:
            self._cache[token] = (now + CACHE_SECONDS, user)
        return user


class DevAuthenticator:
    """Local development only (no Supabase settings): the token is "dev:<email>" and is trusted as it is."""

    def user(self, token: str) -> dict | None:
        if not token.startswith("dev:"):
            return None
        email = token[4:].strip().lower()
        if not EMAIL.match(email):
            return None
        return {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, email)), "email": email}


def current_user(request: Request) -> dict:
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(401, "sign in required")
    try:
        user = request.app.state.authenticator.user(token)
    except AuthUnavailable:
        raise HTTPException(503, "sign-in service unavailable, try again") from None
    if not user:
        raise HTTPException(401, "sign in required")
    role = "teacher" if user["email"] in request.app.state.settings.teachers else "student"
    return {**user, "role": role}


def teacher_only(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "teacher":
        raise HTTPException(403, "teachers only")
    return user
