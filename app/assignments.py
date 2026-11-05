"""Assignments: what a class teacher asks their class to do in the app, by a date.

An assignment (Supabase `math_assignments`) has a title, a note, a due date and 1 to 20 items, each one of
  {"kind": "skill", "id"}                     finish this skill,
  {"kind": "unit_quiz", "unit"}               hand in this unit's summarizing quiz,
  {"kind": "exam", "units": [...]}            take a practice exam over these units,
  {"kind": "worksheet", "id"}                 hand in a solution to this worksheet (app/worksheets.py).
Every item must belong to the units open to the class, and a worksheet to the class itself. Whether an item is done is not stored: the page works it out from
the student's progress and the server's quiz sittings (`assignmentState` in static/math-sky.js), the same way for the
student's home screen and for the teacher's report. The class's teacher (or a manager) writes them; the class reads them.
"""
from __future__ import annotations

import logging
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from .access import has_permission
from .answer_scans import ScanError
from .auth import AuthUnavailable
from .math_skills import algebra9
from .worksheets import WorksheetsUnavailable, drop_ids, submission_public, worksheet_ids, worksheet_public

log = logging.getLogger("mathly.assignments")
MIGRATION = "supabase/migrations/20261104210000_math_assignments.sql"
TABLE = "/rest/v1/math_assignments"
FIELDS = "id,class_id,title,note,due_on,items,created_by_email,created_at,updated_at"
MAX_ITEMS, MAX_TITLE, MAX_NOTE, PER_CLASS = 20, 80, 500, 500
JERUSALEM = ZoneInfo("Asia/Jerusalem")


class AssignmentsUnavailable(RuntimeError):
    pass


class Assignments:
    """The table, through the server's secret key."""

    def __init__(self, auth):
        self.auth = auth
        self._warned = False

    @property
    def configured(self) -> bool:
        return bool(self.auth is not None and getattr(self.auth, "secret", None))

    def _rest(self, query: str = "", method: str = "GET", body=None):
        if not self.configured:
            raise AssignmentsUnavailable("assignments_unavailable")
        try:
            return self.auth._admin(TABLE + query, method, body) or []
        except AuthUnavailable as exc:
            if "answered 404" in str(exc) and not self._warned:
                log.warning("the math_assignments table is missing; apply %s", MIGRATION)
                self._warned = True
            raise AssignmentsUnavailable("assignments_unavailable") from exc

    def for_classes(self, class_ids: list[int]) -> list[dict]:
        """The newest-due assignments of these classes (at most PER_CLASS each)."""
        if not class_ids:
            return []
        out = []
        for class_id in class_ids:
            out += self._rest(f"?select={FIELDS}&class_id=eq.{int(class_id)}&order=due_on.desc&limit={PER_CLASS}")
        return out

    def get(self, assignment_id: str) -> dict | None:
        rows = self._rest(f"?select={FIELDS}&id=eq.{urllib.parse.quote(assignment_id)}")
        return rows[0] if rows else None

    def add(self, row: dict) -> dict:
        return self._rest(f"?select={FIELDS}", "POST", row)[0]

    def update(self, assignment_id: str, fields: dict) -> dict | None:
        rows = self._rest(f"?id=eq.{urllib.parse.quote(assignment_id)}&select={FIELDS}", "PATCH", fields)
        return rows[0] if rows else None

    def remove(self, assignment_id: str) -> None:
        self._rest(f"?id=eq.{urllib.parse.quote(assignment_id)}", "DELETE")


def clean_assignment(body, class_units: list[str], worksheets: set[str] | None = None) -> dict:
    """The fields of an assignment as sent, checked against the class's units and worksheets (their ids; None when they
    cannot be read); HTTPException 400 when something is off."""
    if not isinstance(body, dict):
        raise HTTPException(400, "send the assignment as an object")
    title = " ".join(str(body.get("title") or "").split())
    if not title or len(title) > MAX_TITLE:
        raise HTTPException(400, f"the title is required (up to {MAX_TITLE} characters)")
    note = str(body.get("note") or "").strip()
    if len(note) > MAX_NOTE:
        raise HTTPException(400, f"the note is longer than {MAX_NOTE} characters")
    try:
        due = date.fromisoformat(str(body.get("due_on") or ""))
        if not 2020 <= due.year <= 2100 or len(str(body.get("due_on"))) != 10:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(400, "the due date must be a date (YYYY-MM-DD)") from exc
    raw = body.get("items")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ITEMS:
        raise HTTPException(400, f"an assignment has 1 to {MAX_ITEMS} items")
    graph = algebra9()
    skills = {s["id"]: s["unit"] for s in graph["skills"]}
    quiz_units = {u["id"] for u in graph["units"] if "quiz" in u}
    allowed, items, seen = set(class_units), [], set()
    for item in raw:
        kind = item.get("kind") if isinstance(item, dict) else None
        if kind == "skill":
            ok = skills.get(item.get("id")) in allowed
            clean = {"kind": "skill", "id": item.get("id")}
        elif kind == "unit_quiz":
            ok = item.get("unit") in allowed and item.get("unit") in quiz_units
            clean = {"kind": "unit_quiz", "unit": item.get("unit")}
        elif kind == "exam":
            units = item.get("units")
            ok = isinstance(units, list) and bool(units) and len(set(units)) == len(units) and all(u in allowed for u in units)
            clean = {"kind": "exam", "units": sorted(units) if ok else []}
        elif kind == "worksheet":
            if worksheets is None:
                raise HTTPException(503, "worksheets_unavailable")
            ok = item.get("id") in worksheets
            clean = {"kind": "worksheet", "id": item.get("id")}
        else:
            ok, clean = False, None
        if not ok:
            raise HTTPException(400, "an item is not part of this class's units")
        key = repr(clean)
        if key not in seen:   # the same item twice is one item
            seen.add(key)
            items.append(clean)
    return {"title": title, "note": note, "due_on": due.isoformat(), "items": items}


def public(row: dict, teacher: bool = False) -> dict:
    out = {k: row.get(k) for k in ("id", "class_id", "title", "note", "due_on", "items", "created_at", "updated_at")}
    if teacher:
        out["created_by_email"] = row.get("created_by_email", "")
    return out


def today_in_jerusalem() -> date:
    return datetime.now(JERUSALEM).date()


def install_assignment_routes(app, signed_in, units_of):
    if not hasattr(app.state, "assignments"):
        app.state.assignments = Assignments(app.state.auth)

    def store() -> Assignments:
        return app.state.assignments

    def class_row(class_id: int, user: dict) -> dict:
        """The class, if this account is its teacher or a manager."""
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        try:
            row = next((r for r in app.state.auth.classes() if r.get("id") == class_id), None)
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        if row is None:
            raise HTTPException(404, "class not found")
        if str(user.get("email", "")).lower() not in row.get("teachers", ()) and not has_permission(user, "management.access"):
            raise HTTPException(403, "only the class's teacher can give it assignments")
        return row

    def unavailable(exc: AssignmentsUnavailable) -> HTTPException:
        return HTTPException(503, "assignments_unavailable")

    def reply(value, status=200):
        return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

    def class_worksheets(class_id: int, body) -> set[str] | None:
        """The ids of the class's worksheets, read only when the assignment sent has a worksheet item."""
        items = body.get("items") if isinstance(body, dict) else None
        if not isinstance(items, list) or not any(isinstance(i, dict) and i.get("kind") == "worksheet" for i in items):
            return set()
        store = getattr(app.state, "worksheets", None)
        try:
            return {r["id"] for r in store.of_class(class_id)} if store else None
        except WorksheetsUnavailable:
            return None

    def drop_worksheets(ids) -> None:
        """Deletes worksheets an assignment no longer uses, with their submissions."""
        store = getattr(app.state, "worksheets", None)
        if not ids or store is None:
            return
        try:
            drop_ids(store, ids)
        except WorksheetsUnavailable:
            log.warning("worksheets dropped from an assignment stay until the hourly cleanup")

    def worksheets_only(user, fields, old=None):
        """A teacher gives worksheets only; skills, unit quizzes and practice exams are for managers (developers). Items
        that were already in the assignment stay, so a teacher can still edit an older one."""
        if has_permission(user, "management.access"):
            return
        kept = [i for i in (old or {}).get("items") or [] if i.get("kind") != "worksheet"]
        if any(i["kind"] != "worksheet" and i not in kept for i in fields["items"]):
            raise HTTPException(400, "teachers_give_worksheets_only")

    def note(user, kind, row, label):
        actions = getattr(app.state, "actions", None)
        if actions is not None:
            actions.record(user, kind, f"{label}: {row.get('title', '')}")

    # ---- the class teacher
    @app.get("/api/classes/{class_id}/assignments")
    def list_assignments(class_id: int, user=Depends(signed_in)):
        class_row(class_id, user)
        try:
            return reply({"assignments": [public(r, True) for r in store().for_classes([class_id])]})
        except AssignmentsUnavailable as exc:
            raise unavailable(exc) from exc

    @app.post("/api/classes/{class_id}/assignments")
    def create_assignment(class_id: int, body: dict, user=Depends(signed_in)):
        row = class_row(class_id, user)
        fields = clean_assignment(body, units_of(row), class_worksheets(class_id, body))
        worksheets_only(user, fields)
        try:
            saved = store().add({**fields, "class_id": class_id, "created_by_email": str(user.get("email", "")).lower()})
        except AssignmentsUnavailable as exc:
            raise unavailable(exc) from exc
        note(user, "assignment_saved", saved, row["name"])
        return reply(public(saved, True), 201)

    def owned(class_id: int, assignment_id: str):
        try:
            found = store().get(assignment_id)
        except AssignmentsUnavailable as exc:
            raise unavailable(exc) from exc
        if not found or found.get("class_id") != class_id:
            raise HTTPException(404, "assignment not found")
        return found

    @app.put("/api/classes/{class_id}/assignments/{assignment_id}")
    def update_assignment(class_id: int, assignment_id: str, body: dict, user=Depends(signed_in)):
        row = class_row(class_id, user)
        old = owned(class_id, assignment_id)
        fields = clean_assignment(body, units_of(row), class_worksheets(class_id, body))
        worksheets_only(user, fields, old)
        try:
            saved = store().update(assignment_id, {**fields, "updated_at": datetime.now(timezone.utc).isoformat()})
        except AssignmentsUnavailable as exc:
            raise unavailable(exc) from exc
        if not saved:
            raise HTTPException(404, "assignment not found")
        drop_worksheets(set(worksheet_ids(old.get("items"))) - set(worksheet_ids(saved.get("items"))))
        note(user, "assignment_saved", saved, row["name"])
        return reply(public(saved, True))

    @app.delete("/api/classes/{class_id}/assignments/{assignment_id}")
    def delete_assignment(class_id: int, assignment_id: str, user=Depends(signed_in)):
        row = class_row(class_id, user)
        found = owned(class_id, assignment_id)
        try:
            store().remove(assignment_id)
        except AssignmentsUnavailable as exc:
            raise unavailable(exc) from exc
        drop_worksheets(worksheet_ids(found.get("items")))
        note(user, "assignment_deleted", found, row["name"])
        return reply({"ok": True})

    # ---- the students: their classes' assignments, and when they handed in each unit quiz
    @app.get("/api/math/assignments")
    def my_assignments(user=Depends(signed_in)):
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        classes = [c for c in user.get("classes") or [] if c.get("id") is not None]
        try:
            rows = store().for_classes([c["id"] for c in classes])
        except AssignmentsUnavailable as exc:
            raise unavailable(exc) from exc
        names = {c["id"]: c.get("name", "") for c in classes}
        quiz_units = sorted({i["unit"] for r in rows for i in r["items"] if i.get("kind") == "unit_quiz"})
        sittings = []
        if quiz_units:
            try:
                for unit in quiz_units:
                    sittings += [{"unit_id": s["unit_id"], "submitted_at": s["submitted_at"]}
                                 for s in app.state.answers.quiz(user["id"], "list", unit_id=unit)]
            except ScanError:
                sittings = None   # the server's record could not be read: unit-quiz items cannot be told done
        worksheets, submissions = [], []
        wanted = [w for r in rows for w in worksheet_ids(r.get("items"))]
        if wanted:
            ws = getattr(app.state, "worksheets", None)
            try:
                if ws is None:
                    raise WorksheetsUnavailable("worksheets_unavailable")
                worksheets = [worksheet_public(w) for w in ws.by_ids(wanted)]
                submissions = [submission_public(s) for s in ws.submissions(wanted, user["id"])]
            except WorksheetsUnavailable:
                worksheets = submissions = None   # worksheet items cannot be shown or told done
        return reply({"assignments": [{**public(r), "class_name": names.get(r["class_id"], "")} for r in rows],
                      "sittings": sittings, "worksheets": worksheets, "submissions": submissions,
                      "today": today_in_jerusalem().isoformat()})
