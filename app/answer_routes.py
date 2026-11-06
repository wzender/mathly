"""Authenticated student-facing API for photographed answers."""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import timedelta

from fastapi import BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import ai_usage
from .ai_queue import AiQueue, for_student, may_send
from .answer_scans import AnswerScans, MAX_IMAGE, ScanError, clean_image, public_result, uuid_text
from .answer_grading import AnswerGrader
from .math_photo import PhotoUnavailable
from .quiz_grades import sitting_view
from .quiz_modes import QuizModes, QuizModesUnavailable, hide_results, now_utc, parse_time
from .teacher_ai import LIMIT_CODE as TEACHER_AI_LIMIT, LimitReached, NO_LIMIT
from .teacher_review import MAX_MESSAGE, effective_score, for_student as review_for_student, request_for_student
from .math_skills import algebra9, question_version, quiz_snapshot

log = logging.getLogger("mathly.answer_routes")
DEADLINE_SLACK = timedelta(seconds=30)
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
    if not hasattr(app.state, "quiz_modes"):
        app.state.quiz_modes = QuizModes(app.state.auth)
    if not hasattr(app.state, "open_final"):
        app.state.open_final = lambda _user, _unit: None   # replaced by app/quiz_modes.py

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

    def call(user, action, *, student_view=False, **data):
        """`student_view`: the student is opening the answer, so a teacher's review of it counts as seen."""
        result = app.state.answers.action(user, action, **data)
        if isinstance(result, dict) and result.get("attachment"):
            result["grading_available"] = bool(grading_key())
            try:
                result["grading"] = app.state.answers.grade(user, "get", attempt_id=result["attempt"]["id"])
            except ScanError:
                # A staged deployment must not block saved images or upload receipt.
                result["grading"] = None
                result["grading_available"] = False
            marks = {"review": None, "request": None}   # the teacher's review of the answer, and the student's request
            try:
                marks = app.state.answers.review(user, "get", attempt_id=result["attempt"]["id"])
                if student_view and marks["review"] and not marks["review"].get("seen_at"):
                    app.state.answers.review(user, "seen", attempt_id=result["attempt"]["id"])
            except ScanError:
                pass   # the reviews are not set up yet: the answer still shows
            result["teacher_review"] = review_for_student(marks["review"])
            result["review_request"] = request_for_student(marks["request"])
            check = (result.get("grading") or {}).get("result") if (result.get("grading") or {}).get("state") == "completed" else None
            result["effective_score"] = effective_score((check or {}).get("score"), (marks["review"] or {}).get("score"))
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
        return reply(call(user, "resume", student_view=True, question_id=question["id"], question_version=version,
                          snapshot={"name": question["name"], **sample}, new=body.get("new") is True))

    @app.post("/api/math/quiz-attempts")
    def quiz_attempt(body: dict, user=Depends(student), account=Depends(signed_in)):
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
        start = None
        if body.get("start_id") is not None:   # an answer of a final sitting (app/quiz_modes.py)
            start = final_start(user, body["start_id"], unit["id"])
            if final_over(start):
                raise ScanError(409, "quiz_time_over")
        elif body.get("first") is True and account is not None and app.state.open_final(account, unit["id"]):
            raise ScanError(409, "final_open")   # no practice of a unit while its final quiz waits for the student
        result = call(user, "resume", student_view=True, question_id=f"quiz:{unit['id']}:{index}",
                      question_version=version, snapshot=snapshot, new=body.get("new") is True)
        if start is not None:
            ids = list(start.get("attempt_ids") or [])
            ids += [None] * (index + 1 - len(ids))
            if ids[index] != result["attempt"]["id"]:
                ids[index] = result["attempt"]["id"]
                if None in ids:   # the array has no holes: an attempt not made yet is a placeholder until it is
                    ids = [a or result["attempt"]["id"] for a in ids]
                quiz_modes().update_start(start["id"], {"attempt_ids": ids})
        return reply(result)

    @app.post("/api/math/quiz-sittings")
    def submit_sitting(body: dict, background: BackgroundTasks, user=Depends(student), account=Depends(signed_in)):
        """Hands a unit quiz in: the sitting is kept on the server and its grade is worked out there from the checks
        (app/quiz_grades.py). Sending the same `client_key` again returns the same sitting. A student's answers all go
        to their teacher's queue right here, so none depends on the page staying open to ask for each one.
        With `start_id` it is a final sitting (app/quiz_modes.py): its answers are the start's, and it is the start's
        one sitting."""
        if open_ended_locked():
            raise ScanError(403, "open_ended_locked")
        unit = next((u for u in algebra9()["units"] if u["id"] == body.get("unit_id") and "quiz" in u), None)
        attempts = body.get("attempts")
        if not unit or not isinstance(attempts, list) or len(attempts) != len(unit["quiz"]["questions"]):
            raise ScanError(404, "not_found")
        ids = [uuid_text(a) for a in attempts]
        if body.get("start_id") is not None:
            start = final_start(user, body["start_id"], unit["id"])
            if ids != list(start.get("attempt_ids") or []):
                raise ScanError(409, "invalid_sitting")
            sitting = hand_in_final(user, account, unit, start, time_up=body.get("time_up") is True)
        else:
            sitting = hand_in(user, account, unit, ids, time_up=body.get("time_up") is True,
                              client_key=uuid_text(body.get("client_key")))
            # a practice sitting: sent to the AI now when the class turned that on (app/ai_batches.py); a final waits
            auto = getattr(app.state, "ai_auto_send", None)
            if auto is not None and account is not None and not may_send(account):
                try:
                    auto(account.get("email", ""), [a["attempt_id"] for a in sitting.get("attempts") or []], background)
                except ScanError as exc:
                    log.warning("practice answers not sent automatically: %s", exc.code)
        return JSONResponse({**student_sitting(sitting), **({"code": sitting["code"]} if sitting.get("code") else {})},
                            headers={"Cache-Control": "no-store"})

    def hand_in(user, account, unit, ids, *, time_up, client_key, final=None):
        """Stores the sitting, then puts each photographed answer in the teacher's queue (a student who may not call the
        AI). `final`: the mode, start time and window of a final sitting."""
        sitting = app.state.answers.quiz(user, "submit", unit_id=unit["id"], attempt_ids=ids, time_up=time_up,
                                         client_key=client_key, **(final or {}))
        if account is not None and not may_send(account) and grading_key():
            aids = [a["attempt_id"] for a in sitting.get("attempts") or []]
            code = ""
            for aid in aids:   # a hand-in sent again keeps its number
                try:
                    code = (app.state.ai_queue.for_attempt(user, aid) or {}).get("code") or code
                except ScanError:
                    pass
            code = code or f"{secrets.randbelow(10000):04d}"
            sitting["code"] = code
            for aid in aids:
                try:
                    found = app.state.answers.action(user, "get", attempt_id=aid)
                    if found.get("attachment") and not app.state.answers.grade(user, "get", attempt_id=aid):
                        ask_teacher(user, account, aid, found, True, code)   # automatic: an answer the teacher declined stays declined
                except ScanError as exc:   # one answer that cannot be queued now must not lose the hand-in
                    log.warning("quiz answer not queued for the teacher: %s", exc.code)
        return sitting

    def hand_in_final(user, account, unit, start, *, time_up):
        """A final sitting's hand-in: its key is the start's id, so the page and the server's own hand-in after the
        deadline are the same sitting."""
        ids = list(start.get("attempt_ids") or [])
        if len(ids) != len(unit["quiz"]["questions"]):
            raise ScanError(409, "invalid_sitting")
        sitting = hand_in(user, account, unit, ids, time_up=time_up, client_key=start["id"],
                          final={"mode": "final", "started_at": start["started_at"], "window_id": start["window_id"]})
        if not start.get("sitting_id"):
            try:
                quiz_modes().update_start(start["id"], {"sitting_id": sitting["id"]})
            except QuizModesUnavailable:
                log.warning("a final sitting was handed in but its start was not marked")
        return sitting

    def quiz_modes():
        return app.state.quiz_modes

    def final_start(user, start_id, unit_id=None) -> dict:
        """The student's own final-sitting start; 404 otherwise."""
        try:
            start = quiz_modes().start(uuid_text(start_id))
        except QuizModesUnavailable as exc:
            raise ScanError(503, "quiz_modes_unavailable") from exc
        if not start or start.get("user_id") != user or (unit_id and start.get("unit_id") != unit_id):
            raise ScanError(404, "not_found")
        return start

    def final_over(start) -> bool:
        """No more answers: handed in, or past the deadline (a few seconds' slack for the network)."""
        deadline = parse_time(start.get("deadline"))
        return bool(start.get("sitting_id")) or deadline is None or now_utc() > deadline + DEADLINE_SLACK

    def final_guard(user, attempt):
        """Refuses a photo for an answer of a final sitting that is over, and hands that sitting in if the page did
        not (the answers it has are its answers). Only quiz answers can be of a final sitting."""
        qm = getattr(app.state, "quiz_modes", None)
        if qm is None or not qm.configured or not str((attempt or {}).get("question_id", "")).startswith("quiz:"):
            return
        try:
            start = qm.start_with_attempt(attempt["id"])
        except QuizModesUnavailable:
            return   # no final quizzes without the tables
        if not start or start.get("user_id") != user or not final_over(start):
            return
        if not start.get("sitting_id"):
            unit = next((u for u in algebra9()["units"] if u["id"] == start["unit_id"] and "quiz" in u), None)
            try:
                if unit:
                    hand_in_final(user, None, unit, start, time_up=True)
            except ScanError as exc:
                log.warning("a final sitting past its deadline was not handed in: %s", exc.code)
        raise ScanError(409, "quiz_time_over")

    def released_windows(views) -> set[str]:
        ids = {v["window_id"] for v in views if v and v.get("mode") == "final" and v.get("window_id")}
        if not ids:
            return set()
        try:
            return {w["id"] for w in quiz_modes().windows_by_ids(ids) if w.get("released_at")}
        except QuizModesUnavailable:
            return set()

    def student_sitting(sitting, released=None):
        """A sitting as its student sees it: a final one without its grade until the teacher releases the results."""
        view = sitting_view(sitting)
        if view is None or view.get("mode") != "final":
            return view
        released = released_windows([view]) if released is None else released
        return {**view, "released": True} if view.get("window_id") in released else hide_results(view)

    def hide_unreleased(user, result):
        """An answer of a final sitting whose results are not released: received, no check to see yet."""
        if not isinstance(result, dict) or not str((result.get("attempt") or {}).get("question_id", "")).startswith("quiz:"):
            return result
        qm = getattr(app.state, "quiz_modes", None)
        if qm is None or not qm.configured:
            return result
        try:
            start = qm.start_with_attempt(result["attempt"]["id"])
            window = qm.window(start["window_id"]) if start else None
        except QuizModesUnavailable:
            return result
        if not start or (window and window.get("released_at")):
            return result
        ai = result.get("ai_request")
        return {**result, "unreleased": True, "grading": {"state": "unreleased"} if result.get("grading") else None,
                "teacher_review": None, "effective_score": None,
                "ai_request": {**ai, "result": None} if isinstance(ai, dict) else ai}

    @app.get("/api/math/quiz-sittings")
    def my_sittings(unit_id: str | None = None, user=Depends(student)):
        """The student's own sittings (newest first), each with the grade the server worked out."""
        data = {"unit_id": unit_id} if unit_id else {}
        rows = app.state.answers.quiz(user, "list", **data)
        released = released_windows([sitting_view(s) for s in rows])
        views = [student_sitting(s, released) for s in rows]
        return JSONResponse({"sittings": [v for v in views if v]}, headers={"Cache-Control": "no-store"})

    @app.get("/api/math/answer-attempts/{attempt_id}")
    def get_attempt(attempt_id: str, user=Depends(student)):
        return reply(hide_unreleased(user, call(user, "get", student_view=True, attempt_id=uuid_text(attempt_id))))

    @app.post("/api/math/answer-attempts/{attempt_id}/review-request")
    def ask_review(attempt_id: str, body: dict | None = None, user=Depends(student)):
        """The student asks their teacher to look again at a checked answer (at most one open request per answer)."""
        message = (body or {}).get("message")
        if message is not None and not isinstance(message, str):
            raise ScanError(400, "invalid_message")
        message = (message or "").strip()
        if len(message) > MAX_MESSAGE:
            raise ScanError(400, "message_too_long")
        marks = app.state.answers.review(user, "request", attempt_id=uuid_text(attempt_id), message=message)
        return JSONResponse({"review_request": request_for_student(marks["request"])}, headers={"Cache-Control": "no-store"})

    @app.get("/api/math/teacher-comments")
    def teacher_comments(user=Depends(student)):
        """Answers the teacher reviewed that the student has not opened since."""
        try:
            rows = app.state.answers.review(user, "unseen")
        except ScanError:
            rows = []   # not set up yet: nothing to tell
        return JSONResponse({"comments": rows}, headers={"Cache-Control": "no-store"})

    @app.post("/api/math/answer-attempts/{attempt_id}/grade")
    def grade_answer(attempt_id: str, body: dict | None = None, user=Depends(student), account=Depends(signed_in)):
        result = evaluate_answer(user, uuid_text(attempt_id), automatic=bool(body and body.get("automatic") is True),
                                 account=account)
        if account is None or may_send(account):
            return reply(result)   # a teacher's own check, or sign-in off: nothing to hold back
        return reply(hide_unreleased(user, result))

    def evaluate_answer(user, aid, *, automatic=False, account=None):
        """Checks the answer with the AI. `account`: the signed-in student asking; one who may not call the AI
        (ai_queue.may_send) puts the answer in their teacher's queue instead. None: the teacher's queue sending it."""
        if open_ended_locked():
            raise ScanError(403, "open_ended_locked")   # before any storage read or provider call
        result = app.state.answers.action(user, "get", attempt_id=aid)
        if not result.get("attachment"):
            raise ScanError(409, "answer_required")
        if str(result["attempt"].get("question_id", "")).startswith("worksheet:"):
            raise ScanError(409, "not_gradable")   # homework pages are checked by the teacher, from the hand-in
        existing = app.state.answers.grade(user, "get", attempt_id=aid)
        if existing and (automatic or existing["state"] in ("grading", "completed")):
            return call(user, "get", attempt_id=aid)
        key = grading_key()
        if not key:
            raise ScanError(503, "grading_unavailable", "missing_key", "ANTHROPIC_API_KEY is not set")
        if account is not None and not may_send(account):
            return ask_teacher(user, account, aid, result, automatic)
        quota = getattr(app.state, "teacher_ai", None) or NO_LIMIT
        try:   # a teacher's own check counts toward their 3 a day; the queue's sends are counted where they are sent
            taken = quota.take(account) if account is not None else None
        except LimitReached as exc:
            raise ScanError(429, TEACHER_AI_LIMIT) from exc
        lease = str(uuid.uuid4())
        try:
            grading = app.state.answers.grade(user, "start", attempt_id=aid, lease_id=lease)
        except Exception:
            quota.give_back(taken)
            raise
        if grading["state"] != "grading" or grading["lease_id"] != lease:
            quota.give_back(taken)   # another check is already running
            return call(user, "get", attempt_id=aid)
        try:
            grader = getattr(app.state, "answer_grader", None) or AnswerGrader(key)
            assessment = grader.grade(app.state.answers.read(result["attachment"]["object_key"]),
                                      result["attempt"]["snapshot"])
            ai_usage.record(app.state.auth, user, "grading", assessment.pop("usage", None))
            app.state.answers.grade(user, "complete", attempt_id=aid, lease_id=lease, result=assessment)
            note(user, "answer_graded", result, VERDICTS.get(assessment.get("verdict"), ""))
        except Exception as exc:
            quota.give_back(taken)   # a failed check is not one of the teacher's 3
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
        return call(user, "get", attempt_id=aid)

    def ask_teacher(user, account, aid, result, automatic, code=""):
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
                       "question": str(snapshot.get("question", ""))[:4000], **({"code": code} if code else {})})
            note(user, "ai_request", result)
        return call(user, "get", attempt_id=aid)

    # the teacher's queue sends a student's answer: the same check, with no queue in front of it
    def grade_for_queue(user_id, aid):
        evaluate_answer(user_id, aid)
        return call(user_id, "get", attempt_id=aid)
    app.state.grade_attempt = grade_for_queue

    # Requests a device makes for its own upload (a photo or the board, sent from the same screen): no other device
    # is asked to answer them, so no phone rings and no phone lists them. Kept in memory like Push.notified: a request
    # lives 15 minutes, so a restart only means one may show on a phone.
    @app.post("/api/math/worksheet-attempts")
    async def worksheet_attempt(body: dict, user=Depends(student), account=Depends(signed_in)):
        """A page of a homework worksheet's hand-in, photographed by this device or by the phone like any answer. It is
        only a place for the photo to arrive: the page is added to the hand-in (app/worksheets.py), never checked here."""
        found, _ = await app.state.member_worksheet(account, str(body.get("worksheet_id") or ""))
        snapshot = {"name": f"שיעורי בית: {found['title']}", "type": "open-ended",
                    "question": f"שיעורי בית: {found['title']}. כתבו את הפתרון על דף וצלמו אותו."}
        return reply(await run_in_threadpool(
            lambda: call(user, "resume", student_view=True, question_id=f"worksheet:{found['id']}",
                         question_version=question_version(snapshot), snapshot=snapshot, new=body.get("new") is True)))

    direct_scans: dict[str, None] = {}

    @app.post("/api/math/answer-attempts/{attempt_id}/scans")
    def create_scan(attempt_id: str, body: dict, background_tasks: BackgroundTasks, user=Depends(student)):
        fields = {"attempt_id": uuid_text(attempt_id), "renew": body.get("renew") is True}
        if "question_id" in body:
            fields["question_id"] = str(body["question_id"])
        result = call(user, "create_scan", **fields)
        try:
            final_guard(user, result.get("attempt"))
        except ScanError:   # a final sitting that is over: the request it just made goes too
            if (result.get("scan") or {}).get("id"):
                call(user, "decline", scan_id=result["scan"]["id"])
            raise
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
        found = usable(call(user, "get", scan_id=uuid_text(scan_id)))
        final_guard(user, found.get("attempt"))
        result = usable(call(user, "begin", scan_id=uuid_text(scan_id), key=uuid_text(body.get("key"))))
        response = public_result(result)
        # Only this authenticated upload operation returns the bounded lease.
        response["lease_id"] = result["scan"].get("lease_id")
        return JSONResponse(response, headers={"Cache-Control": "no-store"})

    @app.post("/api/math/answer-scans/{scan_id}/uploads/{lease_id}")
    async def upload(scan_id: str, lease_id: str, photo: UploadFile = File(...), user=Depends(student)):
        sid, lease = uuid_text(scan_id), uuid_text(lease_id)
        data = await photo.read(MAX_IMAGE + 1)
        result = await run_in_threadpool(submit, user, sid, lease, data, photo.content_type)
        note(user, "answer_upload", result)
        # an upload only keeps the answer: nothing is checked, and nothing reaches a teacher, until the student presses
        # "send to the teacher" (POST .../grade), or hands a unit quiz in (submit_sitting)
        return reply(result)

    def submit(user, sid, lease, data, content_type):
        result = usable(call(user, "get", scan_id=sid))
        if result.get("attachment"):
            return result  # an earlier response may have been lost
        final_guard(user, result.get("attempt"))
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
