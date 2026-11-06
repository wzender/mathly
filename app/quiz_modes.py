"""Practice and final unit quizzes.

A practice sitting is what a unit-quiz sitting always was: the student starts one whenever they like, as often as they
like, and the page keeps its clock. It never makes the official grade.

A final sitting is given once. The class teacher opens a window for one unit (`math_quiz_windows`: from, until), and
each student of the class may start one final sitting in it. Starting is recorded here (`math_quiz_starts`), with the
server's start time and deadline (the quiz's minutes plus the photo grace time, cut at the window's end), and the
answer attempts of the sitting in question order. Photos sent after the deadline are refused, and the sitting is then
handed in with what it had. The teacher may give one student another final sitting (`math_quiz_grants`), with its
own end, for example after an absence. A student sees the grade and the checks of a final sitting only after the
teacher releases the window's results.

The official grade of a unit is the grade of the student's latest handed-in final sitting of that unit.

Tables are read and written through the service key (auth._admin), like assignments. Without the migration every
route here answers "quiz_modes_unavailable", and practice quizzes work as before.
"""
from __future__ import annotations

import logging
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from .access import has_permission
from .answer_scans import ScanError
from .auth import AuthUnavailable, ClassConflict
from .math_skills import algebra9

log = logging.getLogger("mathly.quiz_modes")
MIGRATION = "supabase/migrations/20261106090000_math_quiz_modes.sql"
PHOTO_GRACE = timedelta(minutes=10)   # after the writing time, to photograph and hand in (UQ_PHOTO_MIN in math.js)
MAX_WINDOW = timedelta(days=14)
MAX_REASON = 200
W_FIELDS = "id,class_id,unit_id,opens_at,closes_at,released_at,created_by_email,created_at"
G_FIELDS = "id,window_id,student_id,student_email,until,reason,granted_by_email,created_at"
S_FIELDS = "id,window_id,grant_id,user_id,unit_id,started_at,deadline,attempt_ids,sitting_id"


class QuizModesUnavailable(RuntimeError):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value) -> datetime | None:
    """An ISO time with a zone (what the database and the page send); None when it is not one."""
    if not isinstance(value, str) or not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else None


def iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).isoformat()


class QuizModes:
    """The three tables, through the server's secret key."""

    def __init__(self, auth):
        self.auth = auth
        self._warned = False

    @property
    def configured(self) -> bool:
        return bool(self.auth is not None and getattr(self.auth, "secret", None))

    def _rest(self, path: str, method: str = "GET", body=None):
        if not self.configured:
            raise QuizModesUnavailable("quiz_modes_unavailable")
        try:
            return self.auth._admin(path, method, body) or []
        except ClassConflict:
            raise
        except AuthUnavailable as exc:
            if "answered 404" in str(exc) and not self._warned:
                log.warning("the final-quiz tables are missing; apply %s", MIGRATION)
                self._warned = True
            raise QuizModesUnavailable("quiz_modes_unavailable") from exc

    # ---- windows
    def windows(self, class_ids) -> list[dict]:
        ids = sorted({int(c) for c in class_ids})
        if not ids:
            return []
        return self._rest(f"/rest/v1/math_quiz_windows?select={W_FIELDS}&class_id=in.({','.join(map(str, ids))})"
                          "&order=opens_at.desc&limit=200")

    def window(self, window_id: str) -> dict | None:
        rows = self._rest(f"/rest/v1/math_quiz_windows?select={W_FIELDS}&id=eq.{window_id}")
        return rows[0] if rows else None

    def windows_by_ids(self, ids) -> list[dict]:
        ids = sorted(set(ids))
        if not ids:
            return []
        return self._rest(f"/rest/v1/math_quiz_windows?select={W_FIELDS}&id=in.({','.join(ids)})")

    def add_window(self, row: dict) -> dict:
        return self._rest(f"/rest/v1/math_quiz_windows?select={W_FIELDS}", "POST", row)[0]

    def update_window(self, window_id: str, fields: dict) -> dict | None:
        rows = self._rest(f"/rest/v1/math_quiz_windows?id=eq.{window_id}&select={W_FIELDS}", "PATCH", fields)
        return rows[0] if rows else None

    # ---- grants
    def grants(self, window_ids) -> list[dict]:
        ids = sorted(set(window_ids))
        if not ids:
            return []
        return self._rest(f"/rest/v1/math_quiz_grants?select={G_FIELDS}&window_id=in.({','.join(ids)})&order=created_at.asc")

    def grants_of(self, student_id: str) -> list[dict]:
        return self._rest(f"/rest/v1/math_quiz_grants?select={G_FIELDS}&student_id=eq.{student_id}&order=created_at.desc&limit=50")

    def add_grant(self, row: dict) -> dict:
        return self._rest(f"/rest/v1/math_quiz_grants?select={G_FIELDS}", "POST", row)[0]

    # ---- starts
    def starts(self, window_ids=None, user_id: str | None = None) -> list[dict]:
        where = []
        if window_ids is not None:
            ids = sorted(set(window_ids))
            if not ids:
                return []
            where.append(f"window_id=in.({','.join(ids)})")
        if user_id:
            where.append(f"user_id=eq.{user_id}")
        return self._rest(f"/rest/v1/math_quiz_starts?select={S_FIELDS}&{'&'.join(where)}&order=started_at.asc&limit=1000")

    def start(self, start_id: str) -> dict | None:
        rows = self._rest(f"/rest/v1/math_quiz_starts?select={S_FIELDS}&id=eq.{start_id}")
        return rows[0] if rows else None

    def start_with_attempt(self, attempt_id: str) -> dict | None:
        rows = self._rest(f"/rest/v1/math_quiz_starts?select={S_FIELDS}&attempt_ids=cs.%7B{attempt_id}%7D&limit=1")
        return rows[0] if rows else None

    def add_start(self, row: dict) -> dict:
        return self._rest(f"/rest/v1/math_quiz_starts?select={S_FIELDS}", "POST", row)[0]

    def update_start(self, start_id: str, fields: dict) -> dict | None:
        rows = self._rest(f"/rest/v1/math_quiz_starts?id=eq.{start_id}&select={S_FIELDS}", "PATCH", fields)
        return rows[0] if rows else None


# ---- rules that do not need the tables
def quiz_unit(unit_id) -> dict | None:
    return next((u for u in algebra9()["units"] if u["id"] == unit_id and "quiz" in u), None)


def is_open(window: dict, at: datetime) -> bool:
    opens, closes = parse_time(window.get("opens_at")), parse_time(window.get("closes_at"))
    return bool(opens and closes and opens <= at < closes)


def deadline_for(unit: dict, started: datetime, ends: datetime) -> datetime:
    """When a final sitting stops taking answers: its minutes and the photo grace time, at most the window's end."""
    return min(started + timedelta(minutes=unit["quiz"]["minutes"]) + PHOTO_GRACE, ends)


def official_grades(views: list[dict]) -> dict[str, dict]:
    """By unit: the latest handed-in final sitting (its view). Practice sittings never count."""
    out: dict[str, dict] = {}
    for view in sorted((v for v in views if v and v.get("mode") == "final"), key=lambda v: str(v.get("submitted_at") or "")):
        out[view["unit_id"]] = view
    return out


def hide_results(view: dict) -> dict:
    """A final sitting before its results are released, as the student sees it: handed in, nothing more."""
    return {**view, "released": False, "grade": None,
            "questions": [{"points": q["points"], "earned": None, "state": "unreleased", "skills": q.get("skills", [])}
                          for q in view.get("questions") or []]}


def window_public(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "class_id", "unit_id", "opens_at", "closes_at", "released_at", "created_at")}


def grant_public(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "window_id", "student_email", "until", "reason", "created_at")}


def start_public(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "window_id", "grant_id", "unit_id", "started_at", "deadline",
                                    "attempt_ids", "sitting_id")}


def install_quiz_mode_routes(app, signed_in, units_of):
    if not hasattr(app.state, "quiz_modes"):
        app.state.quiz_modes = QuizModes(app.state.auth)

    def store() -> QuizModes:
        return app.state.quiz_modes

    def reply(value, status=200):
        return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

    def unavailable() -> HTTPException:
        return HTTPException(503, "quiz_modes_unavailable")

    def record(user, kind, label):
        actions = getattr(app.state, "actions", None)
        if actions is not None:
            actions.record(user, kind, label)

    def classes() -> list[dict]:
        try:
            return app.state.auth.classes()
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    def class_row(class_id: int, user) -> dict:
        """The class, if this account is its teacher or a manager."""
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        row = next((r for r in classes() if r.get("id") == class_id), None)
        if row is None:
            raise HTTPException(404, "class not found")
        if str(user.get("email", "")).lower() not in row.get("teachers", ()) and not has_permission(user, "management.access"):
            raise HTTPException(403, "only the class's teacher can give final quizzes")
        return row

    def owned_window(class_id: int, window_id: str) -> dict:
        try:
            found = store().window(str(uuid.UUID(window_id)))
        except ValueError as exc:
            raise HTTPException(404, "window not found") from exc
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        if not found or found.get("class_id") != class_id:
            raise HTTPException(404, "window not found")
        return found

    # ---- the class teacher
    @app.get("/api/classes/{class_id}/quiz-windows")
    def list_windows(class_id: int, user=Depends(signed_in)):
        class_row(class_id, user)
        try:
            windows = store().windows([class_id])
            ids = [w["id"] for w in windows]
            grants, starts = store().grants(ids), store().starts(ids)
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        return reply({"windows": [window_public(w) for w in windows], "grants": [grant_public(g) for g in grants],
                      "starts": [{**start_public(s), "user_id": s.get("user_id")} for s in starts],
                      "now": iso(now_utc())})

    @app.post("/api/classes/{class_id}/quiz-windows")
    def open_window(class_id: int, body: dict, user=Depends(signed_in)):
        row = class_row(class_id, user)
        unit = quiz_unit(body.get("unit_id"))
        if not unit or unit["id"] not in units_of(row):
            raise HTTPException(400, "the unit is not a quiz unit of this class")
        opens, closes = parse_time(body.get("opens_at")), parse_time(body.get("closes_at"))
        if not opens or not closes:
            raise HTTPException(400, "opens_at and closes_at are times with a zone")
        if closes <= opens or closes - opens > MAX_WINDOW or closes <= now_utc():
            raise HTTPException(400, "the window must end after it opens, in the future, within 14 days")
        if closes - opens < timedelta(minutes=unit["quiz"]["minutes"]):
            raise HTTPException(400, "the window is shorter than the quiz")
        try:
            if any(w["unit_id"] == unit["id"] and parse_time(w["closes_at"]) > now_utc() for w in store().windows([class_id])):
                raise HTTPException(409, "window_already_open")
            saved = store().add_window({"class_id": class_id, "unit_id": unit["id"], "opens_at": iso(opens),
                                        "closes_at": iso(closes), "created_by_email": str(user.get("email", "")).lower()})
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        record(user, "quiz_window_opened", f"{row.get('name', '')}: {unit['name']}")
        return reply(window_public(saved), 201)

    @app.post("/api/classes/{class_id}/quiz-windows/{window_id}/close")
    def close_window(class_id: int, window_id: str, user=Depends(signed_in)):
        class_row(class_id, user)
        found = owned_window(class_id, window_id)
        at = now_utc()
        if parse_time(found["closes_at"]) <= at:
            return reply(window_public(found))
        if parse_time(found["opens_at"]) > at:   # not opened yet: it ends before it opens
            fields = {"opens_at": iso(at - timedelta(seconds=1)), "closes_at": iso(at)}
        else:
            fields = {"closes_at": iso(at)}
        try:
            saved = store().update_window(found["id"], fields)
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        return reply(window_public(saved or found))

    @app.post("/api/classes/{class_id}/quiz-windows/{window_id}/release")
    def release_window(class_id: int, window_id: str, user=Depends(signed_in)):
        row = class_row(class_id, user)
        found = owned_window(class_id, window_id)
        if found.get("released_at"):
            return reply(window_public(found))
        try:
            saved = store().update_window(found["id"], {"released_at": iso(now_utc())})
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        unit = quiz_unit(found["unit_id"])
        record(user, "quiz_results_released", f"{row.get('name', '')}: {unit['name'] if unit else found['unit_id']}")
        return reply(window_public(saved or found))

    @app.post("/api/classes/{class_id}/quiz-windows/{window_id}/grants")
    def grant(class_id: int, window_id: str, body: dict, user=Depends(signed_in)):
        row = class_row(class_id, user)
        found = owned_window(class_id, window_id)
        email = str(body.get("student_email") or "").strip().lower()
        if not email or email not in row.get("emails", ()) or email in row.get("teachers", ()):
            raise HTTPException(400, "the student is not in this class")
        until = parse_time(body.get("until"))
        if not until or until <= now_utc() or until - now_utc() > MAX_WINDOW:
            raise HTTPException(400, "until is a time in the next 14 days")
        reason = " ".join(str(body.get("reason") or "").split())
        if len(reason) > MAX_REASON:
            raise HTTPException(400, f"the reason is up to {MAX_REASON} characters")
        try:
            student_id = app.state.auth.user_ids([email]).get(email)
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        if not student_id:
            raise HTTPException(400, "the student has not signed in yet")
        try:
            saved = store().add_grant({"window_id": found["id"], "student_id": student_id, "student_email": email,
                                       "until": iso(until), "reason": reason,
                                       "granted_by_email": str(user.get("email", "")).lower()})
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        record(user, "quiz_sitting_granted", f"{row.get('name', '')}: {email}")
        return reply(grant_public(saved), 201)

    # ---- the student
    def offers(user: dict, at: datetime | None = None) -> list[dict]:
        """The final sittings open to this student right now, one per unit: from a window of their class, or from a
        grant. Each says whether it was started (and its start), and until when it can be started."""
        at = at or now_utc()
        class_ids = [c["id"] for c in user.get("classes") or [] if c.get("id") is not None]
        windows = store().windows(class_ids)
        grants = [g for g in store().grants_of(user["id"]) if parse_time(g["until"]) > at]
        extra = store().windows_by_ids([g["window_id"] for g in grants if g["window_id"] not in {w["id"] for w in windows}])
        by_id = {w["id"]: w for w in windows + extra}
        starts = store().starts(user_id=user["id"])
        out = []
        for w in windows:
            if not is_open(w, at):
                continue
            mine = next((s for s in starts if s["window_id"] == w["id"] and not s.get("grant_id")), None)
            out.append({"window": window_public(w), "grant": None, "start": start_public(mine) if mine else None,
                        "until": w["closes_at"]})
        for g in grants:
            w = by_id.get(g["window_id"])
            if not w:
                continue
            mine = next((s for s in starts if s.get("grant_id") == g["id"]), None)
            out.append({"window": window_public(w), "grant": grant_public(g), "start": start_public(mine) if mine else None,
                        "until": g["until"]})
        return out

    app.state.final_offers = offers

    def open_final(user: dict, unit_id: str) -> dict | None:
        """A final sitting of this unit the student can start or is in the middle of (not handed in)."""
        try:
            found = offers(user)
        except QuizModesUnavailable:
            return None   # no final quizzes without the tables
        for offer in found:
            if offer["window"]["unit_id"] != unit_id:
                continue
            start = offer["start"]
            if start is None or not start.get("sitting_id"):
                return offer
        return None

    app.state.open_final = open_final

    @app.get("/api/math/quiz-windows")
    def my_windows(user=Depends(signed_in)):
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        try:
            found = offers(user)
            ids = [o["window"]["id"] for o in found]
            # windows of this student's sittings, to say which results are released (the grades page, the quiz intro)
            done = [s for s in store().starts(user_id=user["id"]) if s.get("sitting_id")]
            seen = store().windows_by_ids({s["window_id"] for s in done} - set(ids))
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        return reply({"offers": found, "windows": [window_public(w) for w in seen] + [o["window"] for o in found],
                      "now": iso(now_utc()), "grace_minutes": int(PHOTO_GRACE.total_seconds() // 60)})

    @app.post("/api/math/quiz-sittings/start")
    def start_final(body: dict, user=Depends(signed_in)):
        """Starts (or resumes) the student's final sitting of a unit: the server's start time and deadline."""
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        unit = quiz_unit(body.get("unit_id"))
        if not unit:
            raise HTTPException(404, "not_found")
        at = now_utc()
        try:
            offer = next((o for o in offers(user, at) if o["window"]["unit_id"] == unit["id"]
                          and not (o["start"] or {}).get("sitting_id")), None)
            if offer is None:
                handed = any(s["unit_id"] == unit["id"] and s.get("sitting_id") for s in store().starts(user_id=user["id"]))
                raise HTTPException(409, "final_already_handed_in" if handed else "final_not_open")
            if offer["start"]:
                return reply({"start": offer["start"], "now": iso(at)})   # a reload: the same clock
            ends = parse_time(offer["until"])
            row = {"window_id": offer["window"]["id"], "grant_id": (offer["grant"] or {}).get("id"),
                   "user_id": user["id"], "unit_id": unit["id"], "started_at": iso(at),
                   "deadline": iso(deadline_for(unit, at, ends)), "attempt_ids": []}
            try:
                saved = store().add_start(row)
            except ClassConflict:   # started at the same moment from another tab: that start
                saved = next(s for s in store().starts(user_id=user["id"])
                             if s["window_id"] == row["window_id"] and s.get("grant_id") == row["grant_id"])
        except QuizModesUnavailable as exc:
            raise unavailable() from exc
        record(user, "quiz_final_started", unit["name"])
        return reply({"start": start_public(saved), "now": iso(at)}, 201)
