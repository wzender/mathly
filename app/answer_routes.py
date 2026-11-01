"""Authenticated student-facing API for photographed answers."""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .answer_scans import AnswerScans, MAX_IMAGE, ScanError, clean_image, public_result, uuid_text
from .answer_grading import AnswerGrader
from .math_photo import PhotoUnavailable
from .math_skills import algebra9, question_version

log = logging.getLogger("mathly.answer_routes")


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

    @app.exception_handler(ScanError)
    async def scan_error(_request, exc):
        return JSONResponse({"detail": exc.code}, status_code=exc.status,
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
        return result

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

    @app.get("/api/math/answer-attempts/{attempt_id}")
    def get_attempt(attempt_id: str, user=Depends(student)):
        return reply(call(user, "get", attempt_id=uuid_text(attempt_id)))

    @app.post("/api/math/answer-attempts/{attempt_id}/grade")
    def grade_answer(attempt_id: str, body: dict | None = None, user=Depends(student)):
        return evaluate_answer(user, uuid_text(attempt_id), automatic=bool(body and body.get("automatic") is True))

    def evaluate_answer(user, aid, *, automatic=False):
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
            raise ScanError(503, "grading_unavailable")
        lease = str(uuid.uuid4())
        grading = app.state.answers.grade(user, "start", attempt_id=aid, lease_id=lease)
        if grading["state"] != "grading" or grading["lease_id"] != lease:
            return reply(call(user, "get", attempt_id=aid))
        try:
            grader = getattr(app.state, "answer_grader", None) or AnswerGrader(key)
            assessment = grader.grade(app.state.answers.read(result["attachment"]["object_key"]),
                                      result["attempt"]["snapshot"])
            app.state.answers.grade(user, "complete", attempt_id=aid, lease_id=lease, result=assessment)
        except Exception as exc:
            # Retain both the image and a retryable failure; never award credit on error.
            try:
                app.state.answers.grade(user, "fail", attempt_id=aid, lease_id=lease)
            except ScanError:
                pass  # an uncertain commit may already have stored the successful check
            if isinstance(exc, ScanError):
                raise
            if not isinstance(exc, PhotoUnavailable):
                log.error("answer grader failed: %s", type(exc).__name__)
            raise ScanError(503, "grading_failed") from exc
        return reply(call(user, "get", attempt_id=aid))

    def automatic_grade(user, attempt_id):
        try:
            evaluate_answer(user, attempt_id, automatic=True)
        except ScanError as exc:
            # Upload is already committed. Keep failures separate and retryable.
            log.info("automatic answer grading stopped: %s", exc.code)

    @app.post("/api/math/answer-attempts/{attempt_id}/scans")
    def create_scan(attempt_id: str, body: dict, user=Depends(student)):
        fields = {"attempt_id": uuid_text(attempt_id), "renew": body.get("renew") is True}
        if "question_id" in body:
            fields["question_id"] = str(body["question_id"])
        return reply(call(user, "create_scan", **fields))

    @app.get("/api/math/answer-scans")
    def pending(user=Depends(student)):
        return reply(call(user, "pending"))

    @app.get("/api/math/answer-scans/{scan_id}")
    def get_scan(scan_id: str, user=Depends(student)):
        return reply(call(user, "get", scan_id=uuid_text(scan_id)))

    @app.post("/api/math/answer-scans/{scan_id}/confirm")
    def confirm(scan_id: str, user=Depends(student)):
        return reply(usable(call(user, "confirm", scan_id=uuid_text(scan_id))))

    @app.post("/api/math/answer-scans/{scan_id}/uploads")
    def begin(scan_id: str, body: dict, user=Depends(student)):
        result = usable(call(user, "begin", scan_id=uuid_text(scan_id), key=uuid_text(body.get("key"))))
        response = public_result(result)
        # Only this authenticated upload operation returns the bounded lease.
        response["lease_id"] = result["scan"].get("lease_id")
        return JSONResponse(response, headers={"Cache-Control": "no-store"})

    @app.post("/api/math/answer-scans/{scan_id}/uploads/{lease_id}")
    async def upload(scan_id: str, lease_id: str, background_tasks: BackgroundTasks,
                     photo: UploadFile = File(...), user=Depends(student)):
        sid, lease = uuid_text(scan_id), uuid_text(lease_id)
        data = await photo.read(MAX_IMAGE + 1)
        result = await run_in_threadpool(submit, user, sid, lease, data, photo.content_type)
        if result.get("grading_available") and not result.get("grading"):
            background_tasks.add_task(automatic_grade, user, result["attempt"]["id"])
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
            object_key = f"{user}/{sid}/{lease}/{uuid.uuid4()}.jpg"
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
