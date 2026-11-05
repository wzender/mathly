"""A teacher's daily AI allowance: 3 requests a day (Jerusalem date), whatever they are.

It counts every call to the AI a teacher makes: a problem they photograph, an answer of their own they check, and a
student's request they send from the AI queue. A call that fails (the AI could not answer, or could not read the
photo) is given back. Developers have no limit. Students are not counted here: they never call the AI themselves
(app/ai_queue.py), and their own daily limits stay as they are.

The counts are kept in memory, like the daily photo counts in main.py, so they start again after a restart.
"""
from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

DAILY = 3
LIMIT_CODE = "teacher_ai_limit"
MESSAGE = f"הגעתם למכסה של {DAILY} בקשות AI ביום. אפשר לנסות שוב מחר."
JERUSALEM = ZoneInfo("Asia/Jerusalem")


def is_teacher(user: dict | None) -> bool:
    """Whether the allowance applies: a signed-in teacher (the role, or a class's teacher) who is not a developer."""
    if not user or not user.get("email") or "developer" in (user.get("roles") or ()):
        return False
    email = str(user["email"]).lower()
    return bool(user.get("teacher")) or any(email in (row.get("teachers") or ()) for row in user.get("classes") or [])


class TeacherQuota:
    def __init__(self, daily: int = DAILY):
        self.daily, self.counts, self._lock = daily, {}, threading.Lock()

    def _key(self, user: dict) -> tuple[str, str]:
        return str(user["email"]).lower(), datetime.now(JERUSALEM).date().isoformat()

    def take(self, user: dict | None):
        """Counts one request; the key to give it back with. None: the account has no limit. LimitReached: none left."""
        if not is_teacher(user):
            return None
        key = self._key(user)
        with self._lock:
            used = self.counts.get(key, 0)
            if used >= self.daily:
                raise LimitReached()
            self.counts[key] = used + 1
        return key

    def give_back(self, key) -> None:
        if key is None:
            return
        with self._lock:
            if self.counts.get(key, 0) > 0:
                self.counts[key] -= 1

    def left(self, user: dict | None) -> int | None:
        """Requests left today; None when the account has no limit."""
        if not is_teacher(user):
            return None
        with self._lock:
            return max(0, self.daily - self.counts.get(self._key(user), 0))


class LimitReached(Exception):
    pass


class NoLimit(TeacherQuota):
    """Stands in where no allowance is kept (an app without one): nothing is counted."""

    def take(self, user):
        return None


NO_LIMIT = NoLimit()
