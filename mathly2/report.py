"""The morning report (דוח בוקר): what was practised on one Israel day (yesterday by default), for the developer's daily message.

    GET /api/dev/report?day=YYYY-MM-DD

Read by the developer, or with `Authorization: Bearer <REPORT_TOKEN>` (a scheduled job cannot sign in with Google). Without REPORT_TOKEN
set, only the developer can read it. It carries counts only, by class, never a student's name or email."""
from __future__ import annotations

import secrets
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

from . import clock

router = APIRouter(prefix="/api/dev")
KINDS = ("lesson_round", "onthego_round", "mistakes_round", "quiz", "exercise_test", "simulation")


def _allowed(request: Request) -> None:
    """The report's key, else a signed-in developer."""
    token = request.app.state.settings.report_token
    header = request.headers.get("authorization", "")
    given = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if token and given and secrets.compare_digest(given, token):
        return
    from .auth import signed_in
    from .status import developer
    developer(request, signed_in(request))


def build(store, day: date) -> dict:
    """The day's numbers: practice answers (right ones too), the people who practised, the attempts started and finished by kind, each
    class's share, and the week up to that day (people and answers per day)."""
    week = store.activity_since(day - timedelta(days=6))
    today = [r for r in week if r["day"] == day]
    correct = store.correct_on(day)
    started = store.attempts_started_on(day)
    kinds = {k: {"started": 0, "finished": 0} for k in KINDS}
    for a in started:
        row = kinds.setdefault(a["kind"], {"started": 0, "finished": 0})
        row["started"] += 1
        row["finished"] += 1 if a["submitted_at"] else 0
    answers_by = {r["user_id"]: r["answers"] for r in today}
    active = {r["user_id"] for r in today if r["answers"] or r["attempts"]}
    classes = []
    for klass in store.classes():
        ids = {m["user_id"] for m in store.members(klass["id"]) if m.get("user_id")}
        members = len(store.members(klass["id"]))
        classes.append({"name": klass["name"], "students": members, "active": len(ids & active),
                        "answers": sum(answers_by.get(u, 0) for u in ids)})
    per_day = Counter()
    people = Counter()
    for r in week:
        per_day[r["day"]] += r["answers"]
        people[r["day"]] += 1 if (r["answers"] or r["attempts"]) else 0
    days = [day - timedelta(days=i) for i in range(6, -1, -1)]
    total = sum(answers_by.values())
    return {"day": day.isoformat(), "answers": total, "correct": sum(correct.values()), "people": len(active),
            "kinds": kinds, "classes": sorted(classes, key=lambda c: -c["answers"]),
            "week": [{"day": d.isoformat(), "people": people[d], "answers": per_day[d]} for d in days]}


@router.get("/report")
def report(request: Request, day: str | None = Query(None, max_length=10)) -> dict:
    _allowed(request)
    try:
        when = date.fromisoformat(day) if day else clock.school_day() - timedelta(days=1)
    except ValueError:
        raise HTTPException(422, "תאריך לא תקין") from None
    return build(request.app.state.store, when)
