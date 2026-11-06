"""AI checks of student work for a whole class (app/ai_batches.py): a class's daily budget instead of the teacher's own
3 requests, given back when a check fails or cannot read the photo; a batch of one scope, partial when the budget is
short; automatic practice checks when the class turns them on; and worksheet suggestions the student never sees."""
import asyncio
import uuid

import pytest

from app.ai_batches import ClassBudget
from app.answer_grading import validate_assessment
from app.main import create_app
from app.math_skills import algebra9, question_version, quiz_snapshot
from scan_support import OTHER, OWNER, answer_store, postgres_server  # noqa: F401
from test_ai_queue import STRANGER, ClassAuth, MemoryQueue, grading_on, mail  # noqa: F401  (grading_on: autouse)
from test_answer_grading import assessment
from test_quiz_modes import client, photograph

T = next(u for u in algebra9()["units"] if u["id"] == "t")


class MemoryBudget(ClassBudget):
    configured = True

    def __init__(self):
        self.used, self.batches = {}, []

    def take(self, class_id, n, limit, day=None):
        have = self.used.get(class_id, 0)
        got = max(0, min(n, limit - have))
        self.used[class_id] = have + got
        return got

    def give(self, class_id, n=1, day=None):
        self.used[class_id] = max(0, self.used.get(class_id, 0) - n)

    def usage(self, class_ids, since):
        from app.ai_batches import today
        return [{"class_id": c, "day": today().isoformat(), "used": u} for c, u in self.used.items() if c in set(class_ids)]

    def add_batch(self, row):
        self.batches.append(row)
        return {"id": str(uuid.uuid4())}


class BudgetAuth(ClassAuth):
    limit, auto = 150, False

    def classes(self, fresh=False):
        rows = super().classes()
        rows[0] = {**rows[0], "lessons": ["t"], "ai_daily_checks": self.limit, "auto_send_practice": self.auto}
        return rows

    def save_class_settings(self, class_id, fields):
        self.saved = (class_id, fields)


@pytest.fixture
def school(answer_store):
    auth = BudgetAuth()
    app = create_app(auth=auth)
    app.state.answers, app.state.ai_queue, app.state.class_budget = answer_store, MemoryQueue(), MemoryBudget()
    verdicts = []

    class Grader:
        def grade(self, image, snapshot):
            score = verdicts.pop(0) if verdicts else 100
            return validate_assessment(assessment(score=0, readable=False) if score is None else assessment(score=score))
    app.state.answer_grader = Grader()
    return app, auth, verdicts


async def practice(student, photos=4):
    """A practice sitting of unit t handed in by OWNER, a student: its photographed answers wait in the queue."""
    ids = []
    for i in range(len(T["quiz"]["questions"])):
        r = await student.post("/api/math/quiz-attempts", json={"unit": "t", "index": i, "new": True, "first": i == 0,
                                                               "question_version": question_version(quiz_snapshot(T, i))})
        ids.append(r.json()["attempt"]["id"])
    for aid in ids[:photos]:
        assert (await photograph(student, aid)).status_code == 200
    r = await student.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "client_key": str(uuid.uuid4())})
    assert r.status_code == 200, r.text
    return ids


def test_a_single_check_of_a_students_answer_uses_the_class_budget_not_the_teachers_own(school):
    app, auth, verdicts = school
    queue, budget = app.state.ai_queue, app.state.class_budget

    async def run():
        async with client(app, OWNER) as student, client(app, OTHER) as teacher:
            await practice(student, photos=2)
            first, second = [r for r in queue.rows if r["kind"] == "grading"]
            assert (await teacher.post(f"/api/ai-queue/{first['id']}/send")).json()["state"] == "done"
            assert budget.used[1] == 1 and app.state.teacher_ai.left({"email": mail(OTHER), "teacher": True}) == 3
            verdicts.append(None)   # the next photo cannot be read: the check is given back
            assert (await teacher.post(f"/api/ai-queue/{second['id']}/send")).json()["result"]["verdict"] == "unreadable"
            assert budget.used[1] == 1
            auth.limit = 1   # used up
            second["state"] = "pending"
            r = await teacher.post(f"/api/ai-queue/{second['id']}/send")
            assert (r.status_code, r.json()["detail"]) == (429, "class_budget_limit")
    asyncio.run(run())


def test_a_batch_sends_one_scope_oldest_first_and_leaves_the_rest_when_the_budget_is_short(school):
    app, auth, verdicts = school
    queue, budget = app.state.ai_queue, app.state.class_budget
    auth.limit = 3

    async def run():
        async with client(app, OWNER) as student, client(app, OTHER) as teacher, client(app, STRANGER) as stranger:
            await practice(student, photos=4)
            view = (await teacher.get("/api/ai-queue/budget")).json()
            (mine,) = view["classes"]
            assert (mine["limit"], mine["left_today"]) == (3, 3)
            assert mine["scopes"] == [{"key": "unit:t", "label": "בחנים: טכניקה אלגברית 1", "pending": 4}]
            preview = (await teacher.post("/api/ai-queue/batches", json={"class_id": 1, "scope": "unit:t"})).json()
            assert (preview["total"], preview["left"]) == (4, 3) and not budget.used
            assert (await stranger.post("/api/ai-queue/batches", json={"class_id": 1, "scope": "unit:t", "confirm": True})).status_code == 403
            done = (await teacher.post("/api/ai-queue/batches", json={"class_id": 1, "scope": "unit:t", "confirm": True})).json()
            assert (done["sent"], done["later"]) == (3, 1)
            states = [r["state"] for r in sorted(queue.rows, key=lambda r: r["created_at"])]
            assert states == ["done", "done", "done", "pending"]   # the oldest three; the last waits for tomorrow
            assert budget.used[1] == 3 and app.state.teacher_ai.left({"email": mail(OTHER), "teacher": True}) == 3
            assert budget.batches[0]["scope"] == "unit:t" and budget.batches[0]["total"] == 4
    asyncio.run(run())


def test_practice_checks_go_by_themselves_when_the_class_turns_it_on_and_finals_still_wait(school):
    app, auth, verdicts = school
    queue = app.state.ai_queue

    async def run():
        async with client(app, OWNER) as student, client(app, OTHER) as teacher:
            await practice(student, photos=1)
            assert [r["state"] for r in queue.rows] == ["pending"]   # off by default
            assert (await teacher.put("/api/classes/1/ai-settings", json={"auto_send_practice": True})).status_code == 200
            assert auth.saved == (1, {"auto_send_practice": True})
            assert (await teacher.put("/api/classes/1/ai-settings", json={"ai_daily_checks": 500})).status_code == 403   # managers only
            auth.auto = True
            await practice(student, photos=1)
            assert [r["state"] for r in queue.rows] == ["pending", "done"]
    asyncio.run(run())


def test_a_worksheet_suggestion_is_the_teachers_until_saved():
    from app.worksheets import submission_public
    sub = {"id": "s", "worksheet_id": "w", "page_keys": ["k"], "submitted_at": "2026-11-05T09:00:00Z", "state": "submitted",
           "ai_score": 70, "ai_comment": "כמעט", "ai_readable": True, "ai_checked_at": "2026-11-05T10:00:00Z"}
    assert "ai" not in submission_public(sub)                                  # the student's view
    assert submission_public(sub, teacher=True)["ai"]["score"] == 70           # the teacher's review form
    assert submission_public(sub)["score"] is None


def test_a_worksheet_batch_fills_each_submissions_suggestion_and_nothing_reaches_the_student(monkeypatch):
    from test_assignments import STUDENT, TEACHER
    from test_assignments import client as aclient
    from test_worksheets import assign, photos, setup, upload
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    app = setup()
    app.state.class_budget, app.state.ai_queue = MemoryBudget(), MemoryQueue()
    calls = []

    class Grader:
        def grade(self, title, sheet, solution):
            calls.append(title)
            return {"readable": True, "score": 70, "comment": "כמעט", "usage": None}
    app.state.homework_grader = Grader()

    async def run():
        async with aclient(app, TEACHER) as teacher, aclient(app, STUDENT) as student:
            wid = (await upload(teacher)).json()["id"]
            await assign(teacher, wid)
            await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(1))
            (mine,) = (await teacher.get("/api/ai-queue/budget")).json()["classes"]
            assert {"key": f"worksheet:{wid}", "label": "שיעורי בית: דף עבודה – פיתגורס", "pending": 1} in mine["scopes"]
            done = (await teacher.post("/api/ai-queue/batches", json={"class_id": 3, "scope": f"worksheet:{wid}", "confirm": True})).json()
            assert done["sent"] == 1 and calls == ["דף עבודה – פיתגורס"]
            report = (await teacher.get("/api/classes/3/report")).json()
            (sub,) = [s for st in report["students"] for s in st["worksheet_submissions"] or []]
            assert sub["ai"]["score"] == 70 and sub["score"] is None and sub["state"] == "submitted"   # a suggestion only
            seen = (await student.get("/api/math/assignments")).json()["submissions"][0]
            assert "ai" not in seen and seen["score"] is None
            again = (await teacher.get("/api/ai-queue/budget")).json()["classes"][0]["scopes"]
            assert not any(s["key"] == f"worksheet:{wid}" for s in again)   # suggested once: not offered again
    asyncio.run(run())
