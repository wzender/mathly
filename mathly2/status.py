"""The developer's status card: is each part of the system working, which version runs and since when (PRD DEV-5).

Only a developer may read it. Nothing here returns a key or a secret: a setting is reported as set or not set. The database and the
push key are really checked; sign-in, AI and pictures are reported from the settings (checking them would call outside services)."""
from __future__ import annotations

import platform
import time

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from . import clock, version
from .auth import signed_in

router = APIRouter(prefix="/api/dev")

OK, WARN, ERROR, OFF = "ok", "warn", "error", "off"


def _check(key: str, name: str, state: str, detail: str) -> dict:
    return {"key": key, "name": name, "state": state, "detail": detail}


def _database(store, supabase_on: bool) -> dict:
    if not supabase_on:
        return _check("database", "מסד הנתונים", WARN, "זיכרון בלבד: שום דבר לא נשמר אחרי הפעלה מחדש")
    raw = getattr(store, "_store", store)                  # past the cache, so the database itself answers
    started = time.monotonic()
    try:
        raw.roles_of("status-check@mathly.invalid")
    except Exception as exc:                                # any failure is the answer, not a crash of the card
        return _check("database", "מסד הנתונים", ERROR, f"לא ענה ({type(exc).__name__})")
    return _check("database", "מסד הנתונים", OK, f"Supabase ענה תוך {round((time.monotonic() - started) * 1000)} אלפיות שנייה")


def _push(pusher, key: str) -> dict:
    if not key:
        return _check("push", "התראות לטלפון", OFF, "אין מפתח: ההתראות כבויות")
    if not getattr(pusher, "on", False):                    # the key is set but the server could not use it
        return _check("push", "התראות לטלפון", ERROR, "המפתח לא תקין: ההתראות כבויות")
    return _check("push", "התראות לטלפון", OK, "מפתח תקין")


def checks(app) -> list[dict]:
    s, state = app.state.settings, app.state
    bank = state.bank
    return [
        _database(state.store, s.supabase_on),
        _check("sign_in", "התחברות", OK if s.supabase_on else WARN,
               "Google דרך Supabase" if s.supabase_on else "כניסת פיתוח עם כתובת מייל בלבד"),
        _check("bank", "מאגר השאלות", OK, f"{len(bank.lessons)} שיעורים, {len(bank.skills)} מיומנויות"),
        _check("ai", "עזרת AI", OK if s.anthropic_key else OFF, "מפתח מוגדר" if s.anthropic_key else "אין מפתח: העזרה כבויה"),
        _push(state.pusher, s.vapid_private_key),
        _check("pictures", "תמונות תשובה", OK if s.supabase_on else WARN,
               f"דלי פרטי {s.answer_bucket}" if s.supabase_on else "בזיכרון בלבד"),
        _check("cleanup", "ניקוי שעתי", OK if getattr(state, "cleanup_stop", None) else OFF,
               "פועל" if getattr(state, "cleanup_stop", None) else "לא פועל בלי Supabase"),
    ]


def overall(found: list[dict]) -> str:
    states = {c["state"] for c in found}
    return ERROR if ERROR in states else WARN if WARN in states else OK


def developer(request: Request, user: dict = Depends(signed_in)) -> dict:
    """The "dev.status" permission, which only the developer role has. The developer role comes only from the settings, so it is
    checked there and not through the roles in the database: the card must still open when the database is down."""
    if user["email"].strip().lower() not in request.app.state.settings.developers:
        raise HTTPException(403, "אין הרשאה לפעולה הזו")
    return user


@router.get("/status")
def status(request: Request, user: dict = Depends(developer)) -> dict:
    app = request.app
    found = checks(app)
    now = clock.now()
    started = app.state.started_at
    return {"overall": overall(found), "checks": found, "version": app.state.version,
            "started_at": started.isoformat(), "uptime_seconds": max(0, int((now - started).total_seconds())), "now": now.isoformat(),
            "python": platform.python_version()}


ACTIVITY_DAYS = (7, 30)


def activity(rows: list[dict], last, days: int) -> dict:
    """Per Israel day from `last - days + 1` to `last` (days without activity included, as zeros): how many people were active,
    their practice answers and their started quizzes and tests; and over the whole range, how many different people."""
    first = last - timedelta(days=days - 1)
    per = {first + timedelta(days=i): {"users": set(), "answers": 0, "attempts": 0} for i in range(days)}
    for r in rows:
        if r["day"] in per:
            d = per[r["day"]]
            d["users"].add(r["user_id"])
            d["answers"] += r["answers"]
            d["attempts"] += r["attempts"]
    everyone = set().union(*(d["users"] for d in per.values()))
    return {"from": first.isoformat(), "to": last.isoformat(),
            "days": [{"day": day.isoformat(), "users": len(d["users"]), "answers": d["answers"], "attempts": d["attempts"]}
                     for day, d in per.items()],
            "users": len(everyone), "answers": sum(d["answers"] for d in per.values()),
            "attempts": sum(d["attempts"] for d in per.values())}


@router.get("/activity")
def activity_route(request: Request, days: int = Query(7), user: dict = Depends(developer)) -> dict:
    """Who used the app on each of the last `days` days (7 or 30). Counts only, never who."""
    if days not in ACTIVITY_DAYS:
        raise HTTPException(422, "days must be 7 or 30")
    last = clock.school_day()
    store = request.app.state.store
    return activity(getattr(store, "_store", store).activity_since(last - timedelta(days=days - 1)), last, days)


def setup(app) -> None:
    app.state.version = version.read()
    app.state.started_at = clock.now()
    app.include_router(router)
