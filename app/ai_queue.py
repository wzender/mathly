"""The teacher's AI queue: a student never calls Claude. A teacher reviews each request and sends it.

A student's photographed problem (POST /api/math/photo) or the answer they want checked
(POST /api/math/answer-attempts/{id}/grade, and the automatic check after an upload) becomes a request in the
Supabase table `math_ai_requests`. The class's teacher (the account chosen in the class editor) sees the requests of
their class's students, and a manager sees every request. The teacher looks at the photo and either sends it to the
AI or declines it with an optional note. The student's page shows the request waiting, and then its result.

Who sends straight to the AI, with no queue: accounts with the teacher, admin or developer role, a class's
teacher, and everyone when sign-in is off (local development: there are no students to hold back).
"""
from __future__ import annotations

import base64
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone

from fastapi import Depends
from fastapi.responses import JSONResponse, Response

from .access import has_permission
from .answer_scans import ScanError, uuid_text
from .auth import AuthUnavailable, ClassConflict
from .math_photo import PhotoUnavailable

log = logging.getLogger("mathly.ai_queue")
MIGRATION = "supabase/migrations/20261104090000_math_ai_requests.sql"
TABLE = "/rest/v1/math_ai_requests"
FIELDS = ("id,created_at,user_id,email,kind,state,attempt_id,label,question,result,note,error,"
          "reviewed_by,sent_at,finished_at")
OPEN = ("pending", "sending")
MAX_OPEN = 5                          # a student's requests waiting at once
STALE_SEND = timedelta(minutes=5)     # a send that never finished (a restart) may be sent again after this
RECENT = timedelta(hours=24)          # handled requests stay on the teacher's list this long
DIRECT_ROLES = frozenset({"teacher", "admin", "developer"})


def may_send(user: dict | None) -> bool:
    """Whether this account calls the AI itself. Everyone else asks their teacher."""
    if user is None:
        return True   # sign-in is off
    if DIRECT_ROLES & set(user.get("roles", ())) or "*" in user.get("permissions", ()):
        return True
    email = str(user.get("email", "")).lower()
    return any(email in row.get("teachers", ()) for row in user.get("classes", ()))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp(when: datetime) -> str:
    return urllib.parse.quote(when.isoformat())


class AiQueue:
    def __init__(self, auth):
        self.auth = auth
        self._warned = False

    @property
    def configured(self) -> bool:
        return bool(self.auth is not None and getattr(self.auth, "secret", None))

    def _rest(self, query: str = "", method: str = "GET", body=None):
        if not self.configured:
            raise ScanError(503, "queue_unavailable")
        try:
            return self.auth._admin(TABLE + query, method, body)
        except ClassConflict as exc:
            raise ScanError(409, "already_queued") from exc
        except AuthUnavailable as exc:
            if "answered 404" in str(exc) and not self._warned:
                log.warning("the math_ai_requests table is missing; apply %s", MIGRATION)
                self._warned = True
            else:
                log.warning("AI queue: %s", exc)
            raise ScanError(503, "queue_unavailable") from exc

    # ---- the student's side
    def add(self, row: dict) -> dict:
        """A new pending request. For an answer that already has one open, that one."""
        try:
            return self._rest("?select=" + FIELDS, "POST", row)[0]
        except ScanError as exc:
            if exc.code == "already_queued" and row.get("attempt_id"):
                found = self.for_attempt(row["user_id"], row["attempt_id"])
                if found:
                    return found
            raise

    def for_attempt(self, user_id: str, attempt_id: str) -> dict | None:
        rows = self._rest(f"?select={FIELDS}&user_id=eq.{user_id}&attempt_id=eq.{attempt_id}"
                          "&order=created_at.desc&limit=1")
        return rows[0] if rows else None

    def open_count(self, user_id: str) -> int:
        return len(self._rest(f"?select=id&user_id=eq.{user_id}&state=in.({','.join(OPEN)})&limit={MAX_OPEN + 1}"))

    def mine(self, user_id: str, limit: int = 20) -> list[dict]:
        return self._rest(f"?select={FIELDS}&user_id=eq.{user_id}&kind=eq.photo&order=created_at.desc&limit={limit}")

    def cancel(self, user_id: str, request_id: str) -> dict | None:
        rows = self._rest(f"?id=eq.{request_id}&user_id=eq.{user_id}&state=eq.pending&select={FIELDS}", "PATCH",
                          {"state": "cancelled", "image": None, "finished_at": now()})
        return rows[0] if rows else None

    def reopen(self, request_id: str) -> dict:
        """A failed request the student asks for again goes back to pending, instead of a second request."""
        rows = self._rest(f"?id=eq.{request_id}&state=in.(failed,declined)&select={FIELDS}", "PATCH",
                          {"state": "pending", "error": "", "note": "", "finished_at": None})
        if not rows:
            raise ScanError(409, "request_taken")
        return rows[0]

    # ---- the teacher's side
    def listing(self, emails: set[str] | None, limit: int = 100) -> list[dict]:
        """Open requests, and the ones handled in the last day. `emails`: only these students (None: all)."""
        if emails is not None and not emails:
            return []
        who = ""
        if emails is not None:
            names = ",".join('"' + e.replace('"', "") + '"' for e in sorted(emails))
            who = "&email=in." + urllib.parse.quote(f"({names})", safe="(),")
        since = stamp(datetime.now(timezone.utc) - RECENT)
        return self._rest(f"?select={FIELDS}{who}&or=(state.in.(pending,sending,failed),finished_at.gte.{since})"
                          f"&order=created_at.desc&limit={limit}")

    def get(self, request_id: str, image: bool = False) -> dict | None:
        rows = self._rest(f"?select={FIELDS}{',image' if image else ''}&id=eq.{request_id}")
        return rows[0] if rows else None

    def claim(self, request_id: str, reviewer: str) -> dict:
        """Takes the request for sending. Two teachers clicking at once: one gets it, the other 409."""
        stale = stamp(datetime.now(timezone.utc) - STALE_SEND)
        rows = self._rest(f"?id=eq.{request_id}&or=(state.in.(pending,failed),and(state.eq.sending,sent_at.lt.{stale}))"
                          f"&select={FIELDS},image", "PATCH",
                          {"state": "sending", "sent_at": now(), "reviewed_by": reviewer, "error": ""})
        if not rows:
            raise ScanError(409, "request_taken")
        return rows[0]

    def finish(self, request_id: str, state: str, **fields) -> dict:
        rows = self._rest(f"?id=eq.{request_id}&select={FIELDS}", "PATCH",
                          {"state": state, "finished_at": now(), **fields})
        return rows[0] if rows else {}

    def decline(self, request_id: str, reviewer: str, note: str) -> dict:
        rows = self._rest(f"?id=eq.{request_id}&state=in.(pending,failed)&select={FIELDS}", "PATCH",
                          {"state": "declined", "image": None, "note": note, "reviewed_by": reviewer,
                           "finished_at": now()})
        if not rows:
            raise ScanError(409, "request_taken")
        return rows[0]


def for_student(row: dict | None) -> dict | None:
    """What the student's page reads of a request: no teacher email, no other student's data."""
    if not row:
        return None
    return {k: row.get(k) for k in ("id", "created_at", "kind", "state", "label", "result", "note", "finished_at")}


def install_ai_queue_routes(app, signed_in):
    if not hasattr(app.state, "ai_queue"):
        app.state.ai_queue = AiQueue(app.state.auth)

    def queue() -> AiQueue:
        return app.state.ai_queue

    def account(user=Depends(signed_in)) -> dict:
        if not user or not user.get("id"):
            raise ScanError(401, "sign_in_required")
        return user

    def watched(user: dict) -> set[str] | None:
        """The students whose requests this account reviews; None: everyone's (a manager)."""
        if has_permission(user, "management.access"):
            return None
        email = str(user.get("email", "")).lower()
        try:
            classes = app.state.auth.classes()
        except AuthUnavailable as exc:
            raise ScanError(503, "queue_unavailable") from exc
        out: set[str] = set()
        for row in classes:
            if email in row.get("teachers", ()):
                out |= set(row.get("emails", ())) - set(row.get("teachers", ()))
        return out

    def reviewer(user=Depends(account)) -> dict:
        if not may_send(user) or watched(user) == set():   # a teacher with no class has no one to review
            raise ScanError(403, "teacher_required")
        return user

    def reviewed(user: dict, request_id: str, image: bool = False) -> dict:
        row = queue().get(uuid_text(request_id), image=image)
        emails = watched(user)
        if not row or (emails is not None and row["email"] not in emails):
            raise ScanError(404, "not_found")
        return row

    def failure(code: str, reason: str = "", detail: str = "") -> str:
        """A failed send's `error`: "code|reason|detail", read by the teacher's error details (math.js)."""
        return "|".join([code, reason or "", " ".join((detail or "").split())])[:300]

    def reply(value, status=200):
        return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

    def note(user, kind, row):
        actions = getattr(app.state, "actions", None)
        if actions is not None:
            what = row.get("label") or ("תרגיל מצולם" if row.get("kind") == "photo" else "")
            actions.record(user, kind, " · ".join(filter(None, [what, row.get("email", "")])))

    # ---- the student
    @app.get("/api/math/ai-requests")
    def my_requests(user=Depends(account)):
        return reply({"direct": may_send(user), "requests": [for_student(r) for r in queue().mine(user["id"])]})

    @app.post("/api/math/ai-requests/{request_id}/cancel")
    def cancel_request(request_id: str, user=Depends(account)):
        row = queue().cancel(user["id"], uuid_text(request_id))
        if row is None:
            raise ScanError(409, "request_taken")
        return reply(for_student(row))

    # ---- the teacher
    @app.get("/api/ai-queue")
    def listing(user=Depends(reviewer)):
        rows = queue().listing(watched(user))
        return reply({"requests": rows, "all": has_permission(user, "management.access")})

    @app.get("/api/ai-queue/{request_id}/image")
    def request_image(request_id: str, user=Depends(reviewer)):
        row = reviewed(user, request_id, image=True)
        if row["kind"] == "photo":
            if not row.get("image"):
                raise ScanError(404, "not_found")
            data = base64.b64decode(row["image"])
        else:
            answer = app.state.answers.action(row["user_id"], "get", attempt_id=row["attempt_id"])
            if not answer.get("attachment"):
                raise ScanError(404, "not_found")
            data = app.state.answers.read(answer["attachment"]["object_key"])
        return Response(data, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @app.post("/api/ai-queue/{request_id}/send")
    def send(request_id: str, user=Depends(reviewer)):
        reviewed(user, request_id)   # visibility first: another class's request is "not found"
        row = queue().claim(uuid_text(request_id), user.get("email", ""))
        if row["kind"] == "photo":
            row = send_photo(row)
        else:
            row = send_answer(row)
        note(user, "ai_sent" if row.get("state") == "done" else "ai_failed", row)
        return reply(row)

    def send_photo(row: dict) -> dict:
        from . import ai_usage
        try:
            result = app.state.solve_photo(base64.b64decode(row.get("image") or ""), "image/jpeg")
        except PhotoUnavailable as exc:
            return queue().finish(row["id"], "failed", error=failure("photo_failed", exc.reason, exc.detail))
        except Exception as exc:
            log.error("AI queue photo failed: %s", type(exc).__name__)
            return queue().finish(row["id"], "failed", error=failure(
                "photo_failed", "server_error", f"{type(exc).__name__}: {str(exc)[:200]}"))
        ai_usage.record(app.state.auth, row["user_id"], "photo", result.pop("usage", None))
        return queue().finish(row["id"], "done", result=result, image=None)

    def send_answer(row: dict) -> dict:
        try:
            result = app.state.grade_attempt(row["user_id"], row["attempt_id"])
        except ScanError as exc:
            return queue().finish(row["id"], "failed", error=failure(exc.code, exc.reason, exc.detail))
        grading = (result or {}).get("grading") or {}
        if grading.get("state") == "completed":
            return queue().finish(row["id"], "done", result={"verdict": grading["result"].get("verdict"),
                                                            "score": grading["result"].get("score")})
        return queue().finish(row["id"], "failed", error=failure(grading.get("error") or "grading_failed"))

    @app.post("/api/ai-queue/{request_id}/decline")
    def decline(request_id: str, body: dict | None = None, user=Depends(reviewer)):
        reviewed(user, request_id)
        text = " ".join(str((body or {}).get("note") or "").split())[:500]
        row = queue().decline(uuid_text(request_id), user.get("email", ""), text)
        note(user, "ai_declined", row)
        return reply(row)
