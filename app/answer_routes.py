"""Authenticated student-facing API for photographed answers."""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import ai_usage
from .ai_queue import AiQueue, for_student, may_send
from .answer_scans import AnswerScans, MAX_IMAGE, ScanError, clean_image, public_result, uuid_text
from .answer_grading import AnswerGrader
from .math_photo import PhotoUnavailable
from .quiz_grades import sitting_view
from .math_skills import algebra9, question_version, quiz_snapshot

log = logging.getLogger("mathly.answer_routes")
VERDICTS = {"correct": "נכונה", "partial": "נכונה חלקית", "incorrect": "שגויה",
            "unreadable": "לא קריאה", "needs_review": "דורשת בדיקה"}


def open_ended_locked():
    """Open-ended questions stay locked (no AI grading, no API tokens) unless MATHLY_OPEN_ENDED_LOCKED=0."""
    return os.environ.get("MATHLY_OPEN_ENDED_LOCKED", "1").strip() != "0"


def grading_key():
    if open_ended_locked():
        return ""
    return (os.environ.get("ANTHROPIC_API_KEY", "").strip()
            or os.environ.get("CLAUDE_API_KEY", "").strip())


def install_answer_routes(app, signed_in):
    if not hasattr(app.state, "answers"):
        app.state.answers = AnswerScans(app.state.auth)
    if not hasattr(app.state, "ai_queue"):
        app.state.ai_queue = AiQueue(app.state.auth)

    @app.exception_handler(ScanError)
    async def scan_error(_request, exc):
        body = {"detail": exc.code}
        if exc.reason:
            body.update(reason=exc.reason, error_detail=exc.detail)
        return JSONResponse(body, status_code=exc.status,
                            headers={"Cache-Control": "no-store"})

    def student(user=Depends(signed_in)):
        if not user or not user.get("id"):
            raise ScanError(401, "sign_in_required")
        if not app.state.answers.configured:
            raise ScanError(503, "answer_storage_unavailable")
        return user["id"]

    def call(user, action, **data):
        result = app.state.answers.action(user, action, **data)
        if isinstance(result, dict) and result.get("attachment"):
            result["grading_available"] = bool(grading_key())
            try:
                result["grading"] = app.state.answers.grade(user, "get", attempt_id=result["attempt"]["id"])
            except ScanError:
                # A staged deployment must not block saved images or upload receipt.
                result["grading"] = None
                result["grading_available"] = False
            result["ai_request"] = None   # the teacher's queue (ai_queue.py): this answer's latest request
            if app.state.ai_queue.configured and (result.get("grading") or {}).get("state") != "completed":
                try:
                    result["ai_request"] = for_student(app.state.ai_queue.for_attempt(user, result["attempt"]["id"]))
                except ScanError:
                    pass
        return result

    def note(user, kind, result, extra=""):
        """Adds to Monitoring's recent actions: the question's name, and the verdict of a check."""
        actions = getattr(app.state, "actions", None)
        if actions is not None:
            name = ((result.get("attempt") or {}).get("snapshot") or {}).get("name", "")
            actions.record(user, kind, " · ".join(filter(None, [name, extra])))

    def reply(result):
        return JSONResponse(public_result(result), headers={"Cache-Control": "no-store"})

    def usable(result):
        if not result.get("scan"):
            raise ScanError(404, "not_found")
        if result["scan"]["state"] == "expired":
            raise ScanError(410, "expired")
        return result

    @app.post("/api/math/answer-attempts")
    def resume_attempt(body: dict, user=Depends(student)):
        question = next((s for s in algebra9()["skills"] if s["id"] == body.get("question_id")), None)
        if not question or question.get("sample", {}).get("type") != "open-ended":
            raise ScanError(404, "not_found")
        sample = question["sample"]
        version = question_version(sample)
        if body.get("question_version") != version:
            raise ScanError(409, "question_changed")
        return reply(call(user, "resume", question_id=question["id"], question_version=version,
                          snapshot={"name": question["name"], **sample}, new=body.get("new") is True))

    @app.post("/api/math/quiz-attempts")
    def quiz_attempt(body: dict, user=Depends(student)):
        """An answer to a question of a unit's summarizing quiz: `new` starts the attempt of a new sitting."""
        if open_ended_locked():
            raise ScanError(403, "open_ended_locked")
        unit = next((u for u in algebra9()["units"] if u["id"] == body.get("unit") and "quiz" in u), None)
        index = body.get("index")
        if not unit or type(index) is not int or not 0 <= index < len(unit["quiz"]["questions"]):
            raise ScanError(404, "not_found")
        snapshot = quiz_snapshot(unit, index)
        version = question_version(snapshot)
        if body.get("question_version") != version:
            raise ScanError(409, "question_changed")
        return reply(call(user, "resume", question_id=f"quiz:{unit['id']}:{index}", question_version=version,
                          snapshot=snapshot, new=body.get("new") is True))

    @app.post("/api/math/quiz-sittings")
    def submit_sitting(body: dict, user=Depends(student)):
        """Hands a unit quiz in: the sitting is kept on the server and its grade is worked out there from the checks
        (app/quiz_grades.py). Sending the same `client_key` again returns the same sitting."""
        if open_ended_locked():
            raise ScanError(403, "open_ended_locked")
        unit = next((u for u in algebra9()["units"] if u["id"] == body.get("unit_id") and "quiz" in u), None)
        attempts = body.get("attempts")
        if not unit or not isinstance(attempts, list) or len(attempts) != len(unit["quiz"]["questions"]):
            raise ScanError(404, "not_found")
        sitting = app.state.answers.quiz(user, "submit", unit_id=unit["id"], attempt_ids=[uuid_text(a) for a in attempts],
                                         time_up=body.get("time_up") is True, client_key=uuid_text(body.get("client_key")))
        return JSONResponse(sitting_view(sitting), headers={"Cache-Control": "no-store"})

    @app.get("/api/math/quiz-sittings")
    def my_sittings(unit_id: str | None = None, user=Depends(student)):
        """The student's own sittings (newest first), each with the grade the server worked out."""
        data = {"unit_id": unit_id} if unit_id else {}
        views = [sitting_view(s) for s in app.state.answers.quiz(user, "list", **data)]
        return JSONResponse({"sittings": [v for v in views if v]}, headers={"Cache-Control": "no-store"})

    @app.get("/api/math/answer-attempts/{attempt_id}")
    def get_attempt(attempt_id: str, user=Depends(student)):
        return reply(call(user, "get", attempt_id=uuid_text(attempt_id)))

    @app.post("/api/math/answer-attempts/{attempt_id}/grade")
    def grade_answer(attempt_id: str, body: dict | None = None, user=Depends(student), account=Depends(signed_in)):
        return evaluate_answer(user, uuid_text(attempt_id), automatic=bool(body and body.get("automatic") is True),
                               account=account)

    def evaluate_answer(user, aid, *, automatic=False, account=None):
        """Checks the answer with the AI. `account`: the signed-in student asking; one who may not call the AI
        (ai_queue.may_send) puts the answer in their teacher's queue instead. None: the teacher's queue sending it."""
        if open_ended_locked():
            raise ScanError(403, "open_ended_locked")   # before any storage read or provider call
        result = app.state.answers.action(user, "get", attempt_id=aid)
        if not result.get("attachment"):
            raise ScanError(409, "answer_required")
        existing = app.state.answers.grade(user, "get", attempt_id=aid)
        if existing and (automatic or existing["state"] in ("grading", "completed")):
            return reply(call(user, "get", attempt_id=aid))
        key = grading_key()
        if not key:
            raise ScanError(503, "grading_unavailable", "missing_key", "ANTHROPIC_API_KEY is not set")
        if account is not None and not may_send(account):
            return ask_teacher(user, account, aid, result, automatic)
        lease = str(uuid.uuid4())
        grading = app.state.answers.grade(user, "start", attempt_id=aid, lease_id=lease)
        if grading["state"] != "grading" or grading["lease_id"] != lease:
            return reply(call(user, "get", attempt_id=aid))
        try:
            grader = getattr(app.state, "answer_grader", None) or AnswerGrader(key)
            assessment = grader.grade(app.state.answers.read(result["attachment"]["object_key"]),
                                      result["attempt"]["snapshot"])
            ai_usage.record(app.state.auth, user, "grading", assessment.pop("usage", None))
            app.state.answers.grade(user, "complete", attempt_id=aid, lease_id=lease, result=assessment)
            note(user, "answer_graded", result, VERDICTS.get(assessment.get("verdict"), ""))
        except Exception as exc:
            # Retain both the image and a retryable failure; never award credit on error.
            try:
                app.state.answers.grade(user, "fail", attempt_id=aid, lease_id=lease)
            except ScanError:
                pass  # an uncertain commit may already have stored the successful check
            if isinstance(exc, ScanError):
                raise
            if isinstance(exc, PhotoUnavailable):
                reason, detail = exc.reason or "provider_error", exc.detail
            else:
                log.error("answer grader failed: %s", type(exc).__name__)
                reason, detail = "server_error", f"{type(exc).__name__}: {' '.join(str(exc).split())[:200]}"
            raise ScanError(503, "grading_failed", reason, detail) from exc
        return reply(call(user, "get", attempt_id=aid))

    def ask_teacher(user, account, aid, result, automatic):
        queue = app.state.ai_queue
        if not queue.configured:
            raise ScanError(503, "grading_unavailable")
        latest = queue.for_attempt(user, aid)
        if latest and latest["state"] in ("pending", "sending"):
            pass   # already waiting
        elif latest and automatic:
            pass   # declined, failed or done before: only the student's own click asks again
        elif latest and latest["state"] in ("failed", "declined"):
            queue.reopen(latest["id"])
            note(user, "ai_request", result)
        else:
            snapshot = result["attempt"].get("snapshot") or {}
            queue.add({"user_id": user, "email": str(account.get("email", "")).lower(), "kind": "grading",
                       "attempt_id": aid, "label": str(snapshot.get("name", ""))[:300],
                       "question": str(snapshot.get("question", ""))[:4000]})
            note(user, "ai_request", result)
        return reply(call(user, "get", attempt_id=aid))

    # the teacher's queue sends a student's answer: the same check, with no queue in front of it
    def grade_for_queue(user_id, aid):
        evaluate_answer(user_id, aid)
        return call(user_id, "get", attempt_id=aid)
    app.state.grade_attempt = grade_for_queue

    def automatic_grade(user, attempt_id, account=None):
        try:
            evaluate_answer(user, attempt_id, automatic=True, account=account)
        except ScanError as exc:
            # Upload is already committed. Keep failures separate and retryable.
            log.info("automatic answer grading stopped: %s", exc.code)

    # Requests a device makes for its own upload (a photo or the board, sent from the same screen): no other device
    # is asked to answer them, so no phone rings and no phone lists them. Kept in memory like Push.notified: a request
    # lives 15 minutes, so a restart only means one may show on a phone.
    direct_scans: dict[str, None] = {}

    @app.post("/api/math/answer-attempts/{attempt_id}/scans")
    def create_scan(attempt_id: str, body: dict, background_tasks: BackgroundTasks, user=Depends(student)):
        fields = {"attempt_id": uuid_text(attempt_id), "renew": body.get("renew") is True}
        if "question_id" in body:
            fields["question_id"] = str(body["question_id"])
        result = call(user, "create_scan", **fields)
        if body.get("direct") is True and (sid := (result.get("scan") or {}).get("id")):
            direct_scans[sid] = None
            while len(direct_scans) > 10_000:
                del direct_scans[next(iter(direct_scans))]
            return reply(result)
        push = getattr(app.state, "push", None)
        if push is not None and push.on:
            # the phone may be in a pocket with the app closed: a notification brings the student to the request
            background_tasks.add_task(push.scan_requested, user, result)
        return reply(result)

    @app.get("/api/math/answer-scans")
    def pending(user=Depends(student)):
        return reply([r for r in call(user, "pending") or [] if (r.get("scan") or {}).get("id") not in direct_scans])

    @app.get("/api/math/answer-scans/{scan_id}")
    def get_scan(scan_id: str, user=Depends(student)):
        return reply(call(user, "get", scan_id=uuid_text(scan_id)))

    @app.post("/api/math/answer-scans/{scan_id}/confirm")
    def confirm(scan_id: str, user=Depends(student)):
        return reply(usable(call(user, "confirm", scan_id=uuid_text(scan_id))))

    @app.post("/api/math/answer-scans/{scan_id}/decline")
    def decline(scan_id: str, user=Depends(student)):
        """The phone refuses the request, or the computer withdraws it."""
        return reply(call(user, "decline", scan_id=uuid_text(scan_id)))

    @app.post("/api/math/answer-scans/{scan_id}/uploads")
    def begin(scan_id: str, body: dict, user=Depends(student)):
        result = usable(call(user, "begin", scan_id=uuid_text(scan_id), key=uuid_text(body.get("key"))))
        response = public_result(result)
        # Only this authenticated upload operation returns the bounded lease.
        response["lease_id"] = result["scan"].get("lease_id")
        return JSONResponse(response, headers={"Cache-Control": "no-store"})

    @app.post("/api/math/answer-scans/{scan_id}/uploads/{lease_id}")
    async def upload(scan_id: str, lease_id: str, background_tasks: BackgroundTasks,
                     photo: UploadFile = File(...), user=Depends(student), account=Depends(signed_in)):
        sid, lease = uuid_text(scan_id), uuid_text(lease_id)
        data = await photo.read(MAX_IMAGE + 1)
        result = await run_in_threadpool(submit, user, sid, lease, data, photo.content_type)
        note(user, "answer_upload", result)
        # a quiz answer is graded only once the quiz is handed in (the page asks for it then)
        quiz = str(result.get("attempt", {}).get("question_id", "")).startswith("quiz:")
        if result.get("grading_available") and not result.get("grading") and not quiz:
            background_tasks.add_task(automatic_grade, user, result["attempt"]["id"], account)
        return reply(result)

    def submit(user, sid, lease, data, content_type):
        result = usable(call(user, "get", scan_id=sid))
        if result.get("attachment"):
            return result  # an earlier response may have been lost
        scan = result["scan"]
        if scan["state"] != "uploading" or scan.get("lease_id") != lease:
            raise ScanError(409, "invalid_upload")
        try:
            image = clean_image(data, content_type)
            object_key = app.state.answers.new_key(user, sid, lease)
            app.state.answers.put(object_key, image)
            result = usable(call(user, "finalize", scan_id=sid, lease_id=lease,
                                 object_key=object_key, byte_size=len(image)))
            # Another transfer with the same lease may have finalized first.
            if result["attachment"]["object_key"] != object_key:
                try:
                    app.state.answers.delete(object_key)
                except ScanError:
                    pass  # orphan cleanup is safe even after an uncertain response
            return result
        except ScanError:
            try:
                call(user, "fail", scan_id=sid, lease_id=lease)
            except ScanError:
                pass
            raise

    @app.get("/api/math/answer-attempts/{attempt_id}/image")
    def image(attempt_id: str, user=Depends(student)):
        result = call(user, "get", attempt_id=uuid_text(attempt_id))
        if not result.get("attachment"):
            raise ScanError(404, "not_found")
        return Response(app.state.answers.read(result["attachment"]["object_key"]), media_type="image/jpeg",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
