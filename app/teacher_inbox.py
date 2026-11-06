"""The class teacher's inbox: everything students handed in that waits for the teacher, in one list, oldest first.

Entries are worksheet submissions not checked yet (the current version; a returned one waits for the student), quiz
answers whose check needs the teacher (not checked yet, unreadable, needs review, or, in a final quiz whose results are
not released, the AI's score the teacher has not confirmed), and open requests to look again at a checked answer. It
is read from what the other modules keep (app/worksheets.py, app/quiz_grades.py, app/quiz_modes.py,
app/teacher_review.py); nothing is stored here. A part that cannot be read is left out and named in `unavailable`.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from .access import has_permission
from .answer_scans import ScanError
from .auth import AuthUnavailable
from .math_skills import algebra9
from .quiz_grades import sitting_view

log = logging.getLogger("mathly.teacher_inbox")
JERUSALEM = ZoneInfo("Asia/Jerusalem")
NEEDS_TEACHER = ("waiting", "unreadable", "needs_review")


def jerusalem_day(at: str) -> str:
    try:
        return datetime.fromisoformat(str(at).replace("Z", "+00:00")).astimezone(JERUSALEM).date().isoformat()
    except ValueError:
        return ""


def install_teacher_inbox_routes(app, signed_in):
    def reply(value):
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    def taught(user) -> list[dict]:
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        try:
            rows = app.state.auth.classes()
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        if has_permission(user, "management.access"):
            return rows
        email = str(user.get("email", "")).lower()
        return [r for r in rows if email in (r.get("teachers") or ())]

    def entries_of(row: dict, unavailable: set[str]) -> list[dict]:
        students = [e for e in row.get("emails") or () if e not in (row.get("teachers") or ())]
        try:
            ids = {email: a["id"] for email, a in app.state.auth.user_accounts(students).items()} if students else {}
        except AuthUnavailable:
            unavailable.add("students")
            return []
        email_of = {uid: email for email, uid in ids.items()}
        out: list[dict] = []
        units = {u["id"]: u for u in algebra9()["units"]}

        # worksheets: the current version, handed in and neither checked nor returned
        store = getattr(app.state, "worksheets", None)
        if store is not None:
            from .worksheets import WorksheetsUnavailable, current
            try:
                sheets = {w["id"]: w for w in store.of_class(row["id"])}
                subs = current(store.submissions(list(sheets)))
                assignments = app.state.assignments.for_classes([row["id"]]) if getattr(app.state, "assignments", None) else []
            except (WorksheetsUnavailable, Exception) as exc:   # AssignmentsUnavailable too
                log.warning("inbox: worksheets not read: %s", type(exc).__name__)
                unavailable.add("worksheets")
                subs, sheets, assignments = [], {}, []
            owner = {i["id"]: a for a in assignments for i in a.get("items") or [] if i.get("kind") == "worksheet"}
            for sub in subs:
                state = sub.get("state") or ("checked" if sub.get("checked_at") else "submitted")
                email = email_of.get(sub.get("student_id")) or sub.get("student_email")
                if state != "submitted" or email not in students:
                    continue
                a = owner.get(sub["worksheet_id"]) or {}
                due = a.get("due_on") or ""
                back = next((e.get("return_due_on") for e in sub.get("earlier") or [] if e.get("return_due_on")), None)
                due = max(due, back) if back else due
                out.append({"kind": "worksheet", "class_id": row["id"], "student_email": email,
                            "title": sheets.get(sub["worksheet_id"], {}).get("title", ""), "assignment_id": a.get("id"),
                            "assignment": a.get("title", ""), "worksheet_id": sub["worksheet_id"], "submission_id": sub["id"],
                            "version": sub.get("version") or 1, "note": sub.get("note") or "",
                            "submitted_at": sub.get("submitted_at"), "state": "submitted",
                            "late": bool(due) and jerusalem_day(sub.get("submitted_at")) > due,
                            "ai": bool(sub.get("ai_checked_at"))})

        # quiz answers that need the teacher
        try:
            sittings = app.state.answers.quiz(None, "report", users=list(ids.values())) if ids else []
        except ScanError:
            unavailable.add("quizzes")
            sittings = []
        views = [(s, sitting_view(s)) for s in sittings]
        window_ids = {v["window_id"] for _, v in views if v and v.get("mode") == "final" and v.get("window_id")}
        released = set()
        if window_ids:
            try:
                released = {w["id"] for w in app.state.quiz_modes.windows_by_ids(window_ids) if w.get("released_at")}
            except Exception:
                released = set()
        for raw, view in views:
            if not view:
                continue
            final = view.get("mode") == "final"
            for i, q in enumerate(view["questions"]):
                state = q["state"]
                if state in NEEDS_TEACHER:
                    pass
                elif final and state == "checked" and view.get("window_id") not in released:
                    state = "ai_to_confirm"   # the AI's score, not yet looked at by the teacher, before release
                else:
                    continue
                out.append({"kind": "quiz", "class_id": row["id"], "student_email": email_of.get(raw.get("user_id")),
                            "title": f"{'בוחן מסכם' if final else 'בוחן חיזוק'}: {units.get(view['unit_id'], {}).get('name', view['unit_id'])} · שאלה {i + 1}",
                            "unit_id": view["unit_id"], "window_id": view.get("window_id"), "mode": view.get("mode"),
                            "attempt_id": view["attempts"][i] if i < len(view["attempts"]) else None,
                            "submitted_at": view.get("submitted_at"), "state": state, "late": False})

        # requests to look again
        try:
            requests = app.state.answers.review(None, "requests", users=list(ids.values())) if ids else []
        except ScanError:
            unavailable.add("requests")
            requests = []
        for r in requests:
            out.append({"kind": "request", "class_id": row["id"], "student_email": email_of.get(r.get("user_id")),
                        "title": r.get("question") or "", "attempt_id": r.get("attempt_id"), "message": r.get("message") or "",
                        "submitted_at": r.get("created_at"), "state": "request", "late": False})
        return [e for e in out if e.get("student_email")]

    @app.get("/api/teacher/inbox")
    def inbox(class_id: int | None = None, user=Depends(signed_in)):
        """The open entries of the teacher's classes (a manager: every class), oldest first; `class_id` narrows it."""
        rows = taught(user)
        if class_id is not None:
            rows = [r for r in rows if r.get("id") == class_id]
            if not rows:
                raise HTTPException(403, "only the class's teacher can see its inbox")
        elif not rows:
            raise HTTPException(403, "teacher_required")
        unavailable: set[str] = set()
        entries = [e for r in rows for e in entries_of(r, unavailable)]
        entries.sort(key=lambda e: str(e.get("submitted_at") or ""))
        return reply({"entries": entries, "count": len(entries), "unavailable": sorted(unavailable)})
