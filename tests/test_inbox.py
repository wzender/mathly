"""The class teacher's inbox (GET /api/teacher/inbox): unchecked worksheet versions, quiz answers that need the
teacher, and requests to look again; oldest first; only the teacher's classes."""
import asyncio

from app.main import create_app
from test_assignments import EMAILS, OTHER_TEACHER, STUDENT, TEACHER, MemoryAssignments, client
from test_quiz_modes import MemoryQuizModes
from test_worksheets import MemoryWorksheets, ReportAuth, assign, photos, upload


def attempt(score=None, state="completed", verdict="correct", photo=True):
    return {"attempt_id": f"a-{verdict}-{score}", "has_photo": photo, "grade_state": state, "score": score, "verdict": verdict}


class Answers:
    configured = True

    def __init__(self, sittings, requests):
        self.sittings, self.requests = sittings, requests

    def quiz(self, user_id, action, **data):
        return [s for s in self.sittings if s["user_id"] in data["users"]]

    def review(self, user_id, action, **data):
        return [r for r in self.requests if r["user_id"] in data["users"]]


def test_the_inbox_lists_what_waits_for_the_teacher_oldest_first():
    app = create_app(auth=ReportAuth())
    app.state.assignments, app.state.worksheets = MemoryAssignments(), MemoryWorksheets()
    app.state.quiz_modes = modes = MemoryQuizModes()
    window = modes.add_window({"class_id": 3, "unit_id": "t", "opens_at": "2026-11-01T08:00:00+00:00", "closes_at": "2026-11-01T10:00:00+00:00"})
    practice = {"id": "p1", "user_id": STUDENT, "unit_id": "t", "submitted_at": "2026-11-02T09:00:00Z", "mode": "practice",
                "attempts": [attempt(100), attempt(None, verdict="unreadable"), attempt(100), attempt(None, state=None, verdict=None)]}
    final = {"id": "f1", "user_id": STUDENT, "unit_id": "t", "submitted_at": "2026-11-01T09:00:00Z", "mode": "final", "window_id": window["id"],
             "attempts": [attempt(90), attempt(100), attempt(80), {**attempt(70), "teacher_score": 75}]}
    app.state.answers = Answers([practice, final], [{"user_id": STUDENT, "attempt_id": "a-x", "message": "כתבתי x=4",
                                                     "question": "שאלה 2", "created_at": "2026-11-03T09:00:00Z"}])

    async def check():
        async with client(app, TEACHER) as teacher, client(app, STUDENT) as student, client(app, OTHER_TEACHER) as other:
            wid = (await upload(teacher)).json()["id"]
            await assign(teacher, wid)
            sub = (await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(1), data={"note": "שאלה 3?"})).json()
            got = (await teacher.get("/api/teacher/inbox?class_id=3")).json()
            kinds = [(e["kind"], e["state"]) for e in got["entries"]]
            # the final's 3 AI-scored answers wait to be confirmed (one has the teacher's score); the practice's open two
            assert kinds == [("quiz", "ai_to_confirm")] * 3 + [("quiz", "unreadable"), ("quiz", "waiting"), ("request", "request"),
                                                                ("worksheet", "submitted")]
            sheet = got["entries"][-1]
            assert (sheet["student_email"], sheet["note"], sheet["submission_id"], sheet["late"]) == (EMAILS[STUDENT], "שאלה 3?", sub["id"], False)
            assert got["count"] == 7 and got["unavailable"] == []
            # released: the final's answers no longer wait; returned: the worksheet no longer waits
            modes.update_window(window["id"], {"released_at": "2026-11-04T09:00:00+00:00"})
            await teacher.post(f"/api/classes/3/worksheets/{wid}/submissions/{sub['id']}/return", json={"comment": "לתקן"})
            again = (await teacher.get("/api/teacher/inbox")).json()
            assert [e["kind"] for e in again["entries"]] == ["quiz", "quiz", "request"]
            assert (await other.get("/api/teacher/inbox?class_id=3")).status_code == 403
            assert (await student.get("/api/teacher/inbox")).status_code == 403
    asyncio.run(check())
