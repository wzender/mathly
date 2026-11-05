"""The class teacher's view of the class: each student's path progress, difficulties and grades.

A class has one teacher, chosen from its students (`classes.teachers`). That account, and any manager, can read
GET /api/classes/{id}/report: for each other student of the class, the parts of their saved progress
(app/progress.py) the teacher's page shows. The page works out the rest (stars, mistake patterns) the same way the
student's own page does.

Progress is kept by the student's device, so everything in it is only what the device reports. The unit quizzes'
grades are the exception: they come from the server's own record of each sitting (app/quiz_grades.py), and a score
in the uploaded progress is never passed on.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from .access import has_permission
from .assignments import AssignmentsUnavailable, public as assignment_public
from .worksheets import WorksheetsUnavailable, submission_public, worksheet_public
from .answer_scans import ScanError
from .auth import AuthUnavailable
from .quiz_grades import sitting_view

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
            # no score: the device's copy of a grade is not evidence. `sid` ties a submission to the server's sitting.
            "history": [{k: h.get(k) for k in ("at", "timeUp", "sid")} for h in history or [] if isinstance(h, dict)],
            "going": bool(isinstance(sitting, dict) and sitting.get("started") and not sitting.get("submitted"))}
    return {"done": obj("done"), "gold": obj("gold"), "days": obj("days"), "missed": obj("missed"),
            "seen": obj("seen"), "tries": obj("tries"), "examples": obj("examples"), "slips": items("slips")[-SLIPS_SENT:], "quizzes": quizzes, "uq": unit_quizzes,
            "updated": data.get("updated")}


def server_sittings(app, ids: dict[str, str]):
    """The students' unit-quiz sittings with the server's grades, by email. None when they cannot be read: the report
    then shows no quiz grades, rather than the device's."""
    try:
        raw = app.state.answers.quiz(None, "report", users=list(ids.values())) if ids else []
    except ScanError as exc:
        log.warning("quiz sittings not read: %s", exc.code)
        return None
    email_of = {user_id: email for email, user_id in ids.items()}
    out: dict[str, list] = {email: [] for email in ids}
    for sitting in raw:
        view = sitting_view(sitting)
        if view and sitting.get("user_id") in email_of:
            out[email_of[sitting["user_id"]]].append(view)
    return out


def server_requests(app, ids: dict[str, str]):
    """The students' open requests to look again at a checked answer (app/teacher_review.py), by email. None when
    they cannot be read."""
    try:
        raw = app.state.answers.review(None, "requests", users=list(ids.values())) if ids else []
    except ScanError as exc:
        log.warning("review requests not read: %s", exc.code)
        return None
    email_of = {user_id: email for email, user_id in ids.items()}
    out: dict[str, list] = {email: [] for email in ids}
    for row in raw:
        if row.get("user_id") in email_of:
            out[email_of[row["user_id"]]].append({k: row.get(k) for k in ("attempt_id", "message", "question", "created_at")})
    return out


def server_assignments(app, class_id: int):
    """The class's assignments (the teacher's view of them), or None when they cannot be read."""
    store = getattr(app.state, "assignments", None)
    if store is None:
        return None
    try:
        return [assignment_public(r, True) for r in store.for_classes([class_id])]
    except AssignmentsUnavailable:
        return None


def server_worksheets(app, class_id: int, ids: dict[str, str]):
    """The class's worksheets and each student's (email) submissions, without storage paths; (None, None) when they cannot
    be read."""
    store = getattr(app.state, "worksheets", None)
    if store is None:
        return None, None
    try:
        rows = store.of_class(class_id)
        subs = store.submissions([r["id"] for r in rows])
    except WorksheetsUnavailable:
        return None, None
    email_of = {uid: email for email, uid in ids.items()}
    out: dict[str, list] = {email: [] for email in ids}
    for sub in subs:
        email = email_of.get(sub.get("student_id"))
        if email is not None:
            out[email].append(submission_public(sub))
    return [worksheet_public(r) for r in rows], out


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
            accounts = auth.user_accounts(students) if students else {}
            ids = {email: account["id"] for email, account in accounts.items()}
            rows = auth._admin(f"{TABLE}?select=user_id,data,updated_at&user_id=in.({','.join(ids.values())})") \
                if ids else []
        except AuthUnavailable as exc:
            log.error("class report failed: %s", exc)
            raise HTTPException(503, "report_unavailable") from exc
        by_id = {r["user_id"]: r for r in rows or []}
        sittings = server_sittings(app, ids)
        requests = server_requests(app, ids)
        worksheets, handed = server_worksheets(app, row["id"], ids)
        nicknames = {str(k).lower(): str(v).strip() for k, v in (row.get("nicknames") or {}).items()}
        out = []
        for email in students:
            saved = by_id.get(ids.get(email, ""))
            data = saved.get("data") if saved else None
            name = nicknames.get(email) or accounts.get(email, {}).get("name") or None
            out.append({"email": email, "name": name, "signed_in": email in ids,
                        "progress": report_part(data) if isinstance(data, dict) else None,
                        "saved_at": saved.get("updated_at") if saved else None,
                        "quiz_sittings": None if sittings is None else sittings.get(email, []),
                        "review_requests": [] if requests is None else requests.get(email, []),
                        "worksheet_submissions": None if handed is None else handed.get(email, [])})
        return JSONResponse({"class": {"id": row["id"], "name": row["name"], "lessons": units_of(row)},
                             "students": out, "assignments": server_assignments(app, row["id"]),
                             "worksheets": worksheets},
                            headers={"Cache-Control": "no-store"})
