"""The student's grades page (GET /api/math/my-grades): the server's grades by unit, the official one only from final
sittings and only once released, practice best and latest, checked worksheets, and only the student's own."""
import asyncio
import uuid

import pytest

from app.answer_grading import validate_assessment
from app.main import create_app
from app.math_skills import algebra9, question_version, quiz_snapshot
from scan_support import OTHER, OWNER, answer_store, postgres_server  # noqa: F401
from test_answer_grading import assessment
from test_quiz_modes import EMAILS, MemoryQuizModes, SchoolAuth, at, client, final_attempts, photograph

T = next(u for u in algebra9()["units"] if u["id"] == "t")


class Auth(SchoolAuth):
    developers = frozenset({EMAILS[OWNER]})   # checks straight with the (fake) AI


@pytest.fixture
def graded(answer_store, monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    app = create_app(auth=Auth())
    app.state.answers = answer_store
    app.state.quiz_modes = MemoryQuizModes()

    class Grader:
        def grade(self, image, snapshot):
            return validate_assessment(assessment(score=100))
    app.state.answer_grader = Grader()
    return app


async def practice(c, photos=0):
    ids = []
    for i in range(len(T["quiz"]["questions"])):
        r = await c.post("/api/math/quiz-attempts", json={"unit": "t", "index": i, "new": True, "first": i == 0,
                                                         "question_version": question_version(quiz_snapshot(T, i))})
        ids.append(r.json()["attempt"]["id"])
    for aid in ids[:photos]:
        assert (await photograph(c, aid)).status_code == 200
    got = (await c.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "client_key": str(uuid.uuid4())})).json()
    for aid in ids[:photos]:
        await c.post(f"/api/math/answer-attempts/{aid}/grade", json={})
    return got, ids


def test_grades_by_unit_official_only_from_a_released_final_and_practice_best_and_latest(graded):
    app = graded

    async def run():
        async with client(app, OWNER) as student, client(app, OTHER) as classmate:
            await practice(student, photos=1)      # 25
            await practice(student, photos=0)      # 0, the latest
            window = app.state.quiz_modes.add_window({"class_id": 1, "unit_id": "t", "opens_at": at(-5), "closes_at": at(120)})
            start = (await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})).json()["start"]
            ids = await final_attempts(student, start["id"])
            await photograph(student, ids[0])
            await student.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "start_id": start["id"]})
            await student.post(f"/api/math/answer-attempts/{ids[0]}/grade", json={})
            got = (await student.get("/api/math/my-grades")).json()
            (t,) = [u for u in got["units"] if u["unit_id"] == "t"]
            assert t["practice_best"]["grade"] == 25 and t["practice_latest"]["grade"] == 0
            assert t["official"]["mode"] == "final" and t["official"]["grade"] is None and t["official"]["released"] is False
            assert [s["mode"] for s in t["sittings"]] == ["final", "practice", "practice"]   # newest first
            app.state.quiz_modes.update_window(window["id"], {"released_at": at(0)})
            t = [u for u in (await student.get("/api/math/my-grades")).json()["units"] if u["unit_id"] == "t"][0]
            assert (t["official"]["grade"], t["official"]["released"]) == (25, True)
            # a classmate sees only their own, whatever they ask for
            theirs = (await classmate.get(f"/api/math/my-grades?student_id={OWNER}")).json()
            assert all(u["sittings"] == [] and u["official"] is None for u in theirs["units"])
    asyncio.run(run())


def test_a_sitting_with_an_answer_still_open_has_no_grade(graded):
    app = graded

    async def run():
        async with client(app, OWNER) as student:
            sitting, ids = await practice(student, photos=0)
            # a photo with no check yet: open
            r = await student.post("/api/math/quiz-attempts", json={"unit": "t", "index": 0, "new": True, "first": True,
                                                                   "question_version": question_version(quiz_snapshot(T, 0))})
            assert r.status_code == 200
            ids2 = [r.json()["attempt"]["id"]]
            for i in range(1, 4):
                ids2.append((await student.post("/api/math/quiz-attempts", json={
                    "unit": "t", "index": i, "new": True, "question_version": question_version(quiz_snapshot(T, i))})).json()["attempt"]["id"])
            await photograph(student, ids2[0])
            await student.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids2, "client_key": str(uuid.uuid4())})
            t = [u for u in (await student.get("/api/math/my-grades")).json()["units"] if u["unit_id"] == "t"][0]
            assert (t["practice_latest"]["grade"], t["practice_latest"]["open"]) == (None, 1)
            assert t["practice_best"]["grade"] == 0
    asyncio.run(run())


def test_checked_worksheets_come_with_their_assignment_and_unit():
    from test_assignments import STUDENT, TEACHER, FocusAuth, MemoryAssignments, Sittings
    from test_assignments import client as aclient
    from test_worksheets import MemoryWorksheets, photos, upload
    from app.answer_scans import ScanError

    class NoReviews(Sittings):
        def review(self, *args, **kwargs):
            raise ScanError(503, "review_unavailable")
    app = create_app(auth=FocusAuth())
    app.state.assignments, app.state.answers, app.state.worksheets = MemoryAssignments(), NoReviews(), MemoryWorksheets()
    app.state.quiz_modes = MemoryQuizModes()

    async def run():
        async with aclient(app, TEACHER) as teacher, aclient(app, STUDENT) as student:
            wid = (await upload(teacher)).json()["id"]
            app.state.assignments.add({"class_id": 3, "title": "פילוג", "note": "", "due_on": "2026-11-12", "student_emails": None,
                                       "items": [{"kind": "skill", "id": "t_ext"}, {"kind": "worksheet", "id": wid}]})
            sub = (await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(1))).json()
            await teacher.put(f"/api/classes/3/worksheets/{wid}/submissions/{sub['id']}", json={"score": 90, "comment": "יפה"})
            got = (await student.get("/api/math/my-grades")).json()
            (sheet,) = got["worksheets"]
            assert (sheet["score"], sheet["comment"], sheet["assignment"], sheet["unit_id"], sheet["title"]) == (
                90, "יפה", "פילוג", "t", "דף עבודה – פיתגורס")
            assert got["comments"] is None   # could not be read: said so, the rest still comes
    asyncio.run(run())
