"""The class teacher's view of the class: each student's path progress, difficulties and grades.

A class has one teacher, chosen from its students (`classes.teachers`). That account, and any manager, can read
GET /api/classes/{id}/report: for each other student of the class, the parts of their saved progress
(app/progress.py) the teacher's page shows. The page works out the rest (stars, mistake patterns) the same way the
student's own page does.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from .access import has_permission
from .auth import AuthUnavailable

log = logging.getLogger("mathly.class_report")
TABLE = "/rest/v1/math_progress"
SLIPS_SENT = 300


def report_part(data: dict) -> dict:
    """What the teacher's page reads from a student's progress: finished skills, mistakes, and both kinds of tests."""
    def obj(key):
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    def items(key):
        value = data.get(key)
        return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []

    quizzes = [{k: q.get(k) for k in ("at", "n", "right", "ms", "units")} for q in items("quizzes")]
    unit_quizzes = {}
    for unit, state in obj("uq").items():
        history = state.get("history") if isinstance(state, dict) else None
        sitting = state.get("sitting") if isinstance(state, dict) else None
        unit_quizzes[unit] = {
            "history": [{k: h.get(k) for k in ("at", "score", "timeUp")} for h in history or [] if isinstance(h, dict)],
            "going": bool(isinstance(sitting, dict) and sitting.get("started") and not sitting.get("submitted"))}
    return {"done": obj("done"), "gold": obj("gold"), "days": obj("days"), "missed": obj("missed"),
            "slips": items("slips")[-SLIPS_SENT:], "quizzes": quizzes, "uq": unit_quizzes,
            "updated": data.get("updated")}


def install_class_report_routes(app, signed_in, units_of):
    def class_of(class_id: int, user) -> dict:
        try:
            row = next((r for r in app.state.auth.classes() if r.get("id") == class_id), None)
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        if row is None:
            raise HTTPException(404, "class not found")
        email = str((user or {}).get("email", "")).lower()
        if email not in row.get("teachers", ()) and not has_permission(user, "management.access"):
            raise HTTPException(403, "only the class's teacher can see its report")
        return row

    @app.get("/api/classes/{class_id}/report")
    def class_report(class_id: int, user=Depends(signed_in)):
        if app.state.auth is None:
            raise HTTPException(404, "classes need sign-in")
        row = class_of(class_id, user)
        teachers = set(row.get("teachers", ()))
        students = [email for email in row.get("emails", ()) if email not in teachers]
        auth = app.state.auth
        try:
            ids = auth.user_ids(students) if students else {}
            rows = auth._admin(f"{TABLE}?select=user_id,data,updated_at&user_id=in.({','.join(ids.values())})") \
                if ids else []
        except AuthUnavailable as exc:
            log.error("class report failed: %s", exc)
            raise HTTPException(503, "report_unavailable") from exc
        by_id = {r["user_id"]: r for r in rows or []}
        out = []
        for email in students:
            saved = by_id.get(ids.get(email, ""))
            data = saved.get("data") if saved else None
            out.append({"email": email, "signed_in": email in ids,
                        "progress": report_part(data) if isinstance(data, dict) else None,
                        "saved_at": saved.get("updated_at") if saved else None})
        return JSONResponse({"class": {"id": row["id"], "name": row["name"], "lessons": units_of(row)},
                             "students": out}, headers={"Cache-Control": "no-store"})
