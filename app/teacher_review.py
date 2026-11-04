"""The class teacher's review of a student's open answer, and the student's request to look again.

An open answer (a photographed solution) is checked by the AI; this lets the class's teacher (or a manager) open any
such answer of their students, give it a score of their own and write a comment. Where an answer's score is used, the
teacher's score wins over the AI's (`effective_score`). The AI's check is never edited: the review is kept next to it
(Supabase `math_teacher_reviews`), the latest review of an answer counts and the older ones stay as history.

A student who disagrees with a check asks the teacher to look again (`math_review_requests`, at most one open per
answer and five per student); saving a review closes the request.
"""
from __future__ import annotations

import logging

from fastapi import Depends
from fastapi.responses import JSONResponse, Response

from .access import students_of
from .answer_scans import ScanError, public_result, uuid_text
from .auth import AuthUnavailable

log = logging.getLogger("mathly.teacher_review")
MAX_COMMENT = 1000
MAX_MESSAGE = 300


def effective_score(check_score, teacher_score):
    """The score an answer counts with: the teacher's when they gave one, else the automatic check's (or None)."""
    return teacher_score if type(teacher_score) is int else check_score if type(check_score) is int else None


def clean_review(body) -> tuple[int | None, str]:
    """The score and comment of a review as sent; ScanError when neither is given or either is out of range."""
    body = body if isinstance(body, dict) else {}
    score, comment = body.get("score"), body.get("comment")
    if score is not None and (type(score) is not int or not 0 <= score <= 100):
        raise ScanError(400, "invalid_score")
    if comment is not None and not isinstance(comment, str):
        raise ScanError(400, "invalid_comment")
    comment = (comment or "").strip()
    if len(comment) > MAX_COMMENT:
        raise ScanError(400, "comment_too_long")
    if score is None and not comment:
        raise ScanError(400, "empty_review")
    return score, comment


def for_student(review: dict | None) -> dict | None:
    """A review as the student's page reads it: no teacher email."""
    if not review:
        return None
    return {k: review.get(k) for k in ("score", "comment", "created_at")}


def request_for_student(request: dict | None) -> dict | None:
    if not request:
        return None
    return {k: request.get(k) for k in ("id", "message", "state", "created_at", "closed_at")}


def install_teacher_review_routes(app, signed_in):
    def students(user: dict) -> set[str] | None:
        try:
            return students_of(user, app.state.auth.classes())
        except AuthUnavailable as exc:
            raise ScanError(503, "review_unavailable") from exc

    def teacher(user=Depends(signed_in)) -> dict:
        """A class teacher, or a manager."""
        if not user or not user.get("id"):
            raise ScanError(401, "sign_in_required")
        if not app.state.answers.configured:
            raise ScanError(503, "answer_storage_unavailable")
        if students(user) == set():   # a teacher with no class has no one to review
            raise ScanError(403, "teacher_required")
        return user

    def email_of(user_id: str) -> str:
        try:
            return app.state.auth.user_email(user_id)
        except AuthUnavailable as exc:
            raise ScanError(503, "review_unavailable") from exc

    def owned(user: dict, attempt_id: str) -> tuple[str, str, str]:
        """(attempt id, the student's account id, their email) of an answer this teacher may review."""
        aid = uuid_text(attempt_id)
        owner = app.state.answers.review(None, "owner", attempt_id=aid)
        email = email_of(owner)
        allowed = students(user)
        if allowed is not None and email not in allowed:
            raise ScanError(403, "forbidden")
        return aid, owner, email

    def reply(value, status=200):
        return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

    @app.get("/api/teacher/answers/{attempt_id}")
    def open_answer(attempt_id: str, user=Depends(teacher)):
        aid, owner, email = owned(user, attempt_id)
        found = app.state.answers.action(owner, "get", attempt_id=aid)
        if not found.get("attachment"):
            raise ScanError(409, "answer_required")
        grading = app.state.answers.grade(owner, "get", attempt_id=aid)
        marks = app.state.answers.review(owner, "get", attempt_id=aid)
        shown = public_result({"attempt": found["attempt"], "attachment": found["attachment"], "grading": grading})
        check = (grading or {}).get("result") if (grading or {}).get("state") == "completed" else None
        return reply({**shown, "student": {"email": email}, "review": marks["review"], "request": marks["request"],
                      "effective_score": effective_score((check or {}).get("score"), (marks["review"] or {}).get("score"))})

    @app.get("/api/teacher/answers/{attempt_id}/image")
    def answer_image(attempt_id: str, user=Depends(teacher)):
        aid, owner, _email = owned(user, attempt_id)
        found = app.state.answers.action(owner, "get", attempt_id=aid)
        if not found.get("attachment"):
            raise ScanError(404, "not_found")
        data = app.state.answers.read(found["attachment"]["object_key"])
        return Response(data, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @app.put("/api/teacher/answers/{attempt_id}/review")
    def save_review(attempt_id: str, body: dict, user=Depends(teacher)):
        score, comment = clean_review(body)
        aid, owner, email = owned(user, attempt_id)
        marks = app.state.answers.review(owner, "review", attempt_id=aid, reviewer=user.get("email", ""),
                                         score=score, comment=comment)
        actions = getattr(app.state, "actions", None)
        if actions is not None:
            actions.record(user, "answer_reviewed", email)
        return reply(marks)

    @app.get("/api/teacher/review-requests")
    def review_requests(user=Depends(teacher)):
        """Open requests to look again from this teacher's students (a manager: everyone's)."""
        allowed = students(user)
        try:
            if allowed is None:
                rows, emails = app.state.answers.review(None, "requests"), {}
            else:
                accounts = app.state.auth.user_accounts(sorted(allowed))
                emails = {account["id"]: email for email, account in accounts.items()}
                rows = app.state.answers.review(None, "requests", users=list(emails))
        except AuthUnavailable as exc:
            raise ScanError(503, "review_unavailable") from exc
        for row in rows:
            row["student"] = emails.get(row["user_id"]) or email_of(row["user_id"])
            del row["user_id"]
        return reply({"requests": rows})
