"""The managers' Monitoring tab (ניטור): system health, the server's error log, and open-answer activity.

Practice itself is kept on each student's device, so the activity here is what the server does see: who opened
the app, photographed problems, and open answers with their photo checks. Activity is aggregated and anonymous.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from collections import Counter, deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Query

from . import log_errors
from .answer_routes import grading_key, open_ended_locked
from .auth import AuthUnavailable
from .math_photo import DAILY_PHOTOS

ROOT = Path(__file__).resolve().parent.parent
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")
# period -> (minutes per bar, number of bars)
PERIODS = {"day": (15, 96), "week": (60, 168), "month": (24 * 60, 30)}
SEEN_KEEP = 24 * 3600
RETURN_GAP = 30 * 60  # a sign-in after this long away counts as a new visit
ACTION_KINDS = frozenset({"visit", "photo", "answer_upload", "answer_graded", "class_saved", "class_deleted"})


class ActionLog:
    """The latest actions on the server: what was done, by which account, and when. Kept in memory only,
    so it starts empty after a restart. Labels name the question or class, never a student's answer."""

    def __init__(self, keep: int = 200):
        self._items: deque[dict] = deque(maxlen=keep)
        self.emails: dict[str, str] = {}  # user id -> email, learned at sign-in

    def record(self, user: dict | str | None, kind: str, label: str = "") -> None:
        if isinstance(user, dict):
            if user.get("id") and user.get("email"):
                self.emails[user["id"]] = user["email"]
            email = user.get("email", "")
        else:
            email = self.emails.get(user or "", "")
        self._items.append({"at": time.time(), "kind": kind, "email": email, "label": str(label or "")[:120]})

    def recent(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._items))[:limit]


def build_metadata() -> dict[str, str]:
    """Which code is running: a content hash, when it changed, and the commit when known."""
    files = sorted((ROOT / "app").glob("*.py")) + sorted((ROOT / "static").glob("*.js")) + [ROOT / "static" / "index.html"]
    digest = hashlib.sha1()
    for path in files:
        digest.update(path.read_bytes())
    newest = max(path.stat().st_mtime for path in files)
    commit = next((os.environ[name].strip() for name in ("GIT_COMMIT", "COMMIT_SHA", "SOURCE_VERSION", "SPACE_REVISION")
                   if os.environ.get(name, "").strip()), "")
    message = os.environ.get("GIT_COMMIT_MESSAGE", "").strip()
    if not commit or not message:
        try:
            git = subprocess.run(["git", "log", "-1", "--format=%H%n%s"], cwd=ROOT, check=True,
                                 capture_output=True, text=True, timeout=2).stdout.splitlines()
            commit = commit or (git[0].strip() if git else "")
            message = message or (git[1].strip() if len(git) > 1 else "")
        except (OSError, subprocess.SubprocessError):
            pass
    return {"version": os.environ.get("APP_VERSION", "").strip() or digest.hexdigest()[:7],
            "updated_at": os.environ.get("BUILD_DATE", "").strip()
            or datetime.fromtimestamp(newest, timezone.utc).isoformat(timespec="seconds"),
            "commit": commit or "unknown", "commit_message": message}


def seen_summary(seen: dict[str, float], now: float | None = None) -> dict:
    """How many signed-in accounts reached the server lately. Forgets accounts not seen for a day."""
    now = time.time() if now is None else now
    for user_id, at in list(seen.items()):
        if now - at > SEEN_KEEP:
            seen.pop(user_id, None)
    times = list(seen.values())
    return {"last_5m": sum(now - t <= 300 for t in times), "last_hour": sum(now - t <= 3600 for t in times),
            "last_24h": len(times)}


def photo_summary(counts: dict[tuple[str, str], int], today: str | None = None) -> dict:
    today = today or datetime.now(LOCAL_TZ).date().isoformat()
    used = {email: n for (email, day), n in counts.items() if day == today and n > 0}
    return {"today": sum(used.values()), "students": len(used),
            "at_limit": sum(n >= DAILY_PHOTOS for n in used.values()), "daily_limit": DAILY_PHOTOS}


def _utc(stamp: str) -> datetime:
    # The seconds part only: the fraction's length varies, which older Pythons do not parse.
    return datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def activity_buckets(rows: dict, period: str, now: datetime | None = None) -> dict:
    """Open-answer attempts and active students per bar, and the period's engagement and verdict totals."""
    minutes, slots = PERIODS[period]
    now = now or datetime.now(timezone.utc)
    if minutes == 24 * 60:  # whole local days
        today = now.astimezone(LOCAL_TZ).date()
        starts = [datetime.combine(today - timedelta(days=slots - 1 - i), datetime.min.time(), LOCAL_TZ)
                  for i in range(slots)]
        slot = lambda t: (t.astimezone(LOCAL_TZ).date() - starts[0].date()).days
    else:
        seconds = minutes * 60
        end = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, timezone.utc)
        starts = [end - timedelta(seconds=(slots - 1 - i) * seconds) for i in range(slots)]
        slot = lambda t: int((t - starts[0]).total_seconds() // seconds)
    attempts, students = [0] * slots, [set() for _ in range(slots)]
    days: dict[str, set[date]] = {}
    for row in rows.get("attempts", ()):
        at = _utc(row["created_at"])
        i = slot(at)
        if 0 <= i < slots:
            attempts[i] += 1
            students[i].add(row["user_id"])
            days.setdefault(row["user_id"], set()).add(at.astimezone(LOCAL_TZ).date())
    verdicts: Counter[str] = Counter()
    for row in rows.get("grades", ()):
        if 0 <= slot(_utc(row["created_at"])) < slots:
            verdicts[row.get("verdict") or row.get("state") or "unknown"] += 1
    return {"period": period, "bucket_minutes": minutes,
            "buckets": [{"bucket": start.isoformat(), "attempts": attempts[i], "active_students": len(students[i])}
                        for i, start in enumerate(starts)],
            "summary": {"attempts": sum(attempts), "active_students": len(days),
                        "returning_students": sum(len(d) >= 2 for d in days.values()),
                        "active_days": len({d for ds in days.values() for d in ds}),
                        "checks": sum(verdicts.values()), "verdicts": dict(verdicts)}}


def install_monitoring_routes(app, manager) -> None:
    log_errors.install()
    if not hasattr(app.state, "seen"):
        app.state.seen = {}
    if not hasattr(app.state, "photo_counts"):
        app.state.photo_counts = {}
    if not hasattr(app.state, "actions"):
        app.state.actions = ActionLog()

    @app.get("/api/monitor/summary")
    def monitor_summary(_user: dict = Depends(manager)):
        """Everything the Monitoring summary can tell without a network call."""
        answers = app.state.answers
        return {"build": build_metadata(), "errors": log_errors.COUNTER.summary(),
                "seen": seen_summary(app.state.seen), "actions": app.state.actions.recent(), "photos": photo_summary(app.state.photo_counts),
                "answers": {"storage": answers.configured, "open_ended_locked": open_ended_locked(),
                            "grading": bool(grading_key())},
                "photo_help": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()
                                   or os.environ.get("CLAUDE_API_KEY", "").strip())}

    @app.get("/api/monitor/supabase")
    def monitor_supabase(_user: dict = Depends(manager)):
        """Supabase's sign-in service and database, each timed now. Kept apart because it can be slow."""
        store = app.state.auth
        if store is None:
            missing = {"ok": False, "error": "Supabase is not configured"}
            return {"auth": missing, "db": missing}
        return store.ping()

    @app.get("/api/monitor/activity")
    def monitor_activity(period: str = Query("week", pattern="^(day|week|month)$"), _user: dict = Depends(manager)):
        """Open-answer attempts per bar and photo-check verdicts: counts only, no answers or names."""
        store = app.state.auth
        if store is None or not store.secret:
            return {"period": period, "unavailable": "answer storage is not configured"}
        minutes, slots = PERIODS[period]
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes * slots + 24 * 60)
        try:
            rows = store.answer_activity(since)
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        if rows is None:
            return {"period": period, "unavailable": "the open-answer tables are not installed"}
        return activity_buckets(rows, period)
