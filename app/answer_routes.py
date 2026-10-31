"""Authenticated student-facing API for photographed answers."""
from __future__ import annotations

import uuid

from fastapi import Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .answer_scans import AnswerScans, MAX_IMAGE, ScanError, clean_image, public_result, uuid_text
from .math_skills import algebra9, question_version


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
        return app.state.answers.action(user, action, **data)

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
        if not question or question["sample"].get("type") != "open-ended":
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
    async def upload(scan_id: str, lease_id: str, photo: UploadFile = File(...), user=Depends(student)):
        sid, lease = uuid_text(scan_id), uuid_text(lease_id)
        data = await photo.read(MAX_IMAGE + 1)
        return await run_in_threadpool(submit, user, sid, lease, data, photo.content_type)

    def submit(user, sid, lease, data, content_type):
        result = usable(call(user, "get", scan_id=sid))
        if result.get("attachment"):
            return reply(result)  # an earlier response may have been lost
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
            return reply(result)
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
