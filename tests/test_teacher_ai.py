"""A teacher's 3 AI requests a day: their own photos and checks, and the student requests they send from the queue."""
import asyncio
import pytest

from app.teacher_ai import TeacherQuota, is_teacher
from scan_support import OTHER, OWNER
from scan_support import answer_store, postgres_server  # noqa: F401  (fixtures)
from test_ai_queue import Solver, as_user, grading_on, make_app  # noqa: F401  (grading_on: a fixture)
from test_answer_scans import png


def photo():
    return {"photo": ("p.png", png(), "image/png")}


def test_who_is_counted():
    teacher = {"email": "t@x", "roles": ["student"], "classes": [{"teachers": ["t@x"]}]}
    assert is_teacher(teacher)                                                   # a class's teacher
    assert is_teacher({"email": "r@x", "roles": ["teacher"], "teacher": True, "classes": []})   # the teacher role
    assert not is_teacher({"email": "d@x", "roles": ["developer"], "teacher": True})            # developers: no limit
    assert not is_teacher({"email": "s@x", "roles": ["student"], "classes": [{"teachers": ["t@x"]}]})
    assert not is_teacher(None)
    quota = TeacherQuota()
    keys = [quota.take(teacher) for _ in range(3)]
    assert quota.left(teacher) == 0
    with pytest.raises(Exception):
        quota.take(teacher)
    quota.give_back(keys[0])
    assert quota.left(teacher) == 1 and quota.left({"email": "s@x", "roles": ["student"]}) is None


def test_the_teachers_own_photos_stop_after_three_and_a_failure_is_given_back():
    app = make_app()

    class Unreadable(Solver):
        def solve(self, image, media_type):
            return {"readable": False, "problem": "", "steps": [], "answer": "", "skill": "", "note": "", "usage": None}

    async def check():
        async with as_user(app, OTHER) as teacher:                                     # OTHER teaches class 1
            assert (await teacher.get("/api/me")).json()["ai_left"] == 3
            app.state.photo = Unreadable()
            assert (await teacher.post("/api/math/photo", files=photo())).status_code == 200
            assert (await teacher.get("/api/me")).json()["ai_left"] == 3                # unreadable: not counted
            app.state.photo = Solver()
            for _ in range(3):
                assert (await teacher.post("/api/math/photo", files=photo())).status_code == 200
            refused = await teacher.post("/api/math/photo", files=photo())
            assert refused.status_code == 429 and "3 בקשות AI ביום" in refused.json()["detail"]
            assert len(app.state.photo.calls) == 3 and (await teacher.get("/api/me")).json()["ai_left"] == 0
        async with as_user(app, OWNER) as student:
            assert (await student.get("/api/me")).json()["ai_left"] is None             # students are not counted here
    asyncio.run(check())


def test_sending_from_the_queue_counts_and_stops_at_three():
    app = make_app()
    queue = app.state.ai_queue

    async def check():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            ids = [(await student.post("/api/math/photo", files=photo())).json()["request"]["id"] for _ in range(4)]
            for rid in ids[:3]:
                assert (await teacher.post(f"/api/ai-queue/{rid}/send")).json()["state"] == "done"
            refused = await teacher.post(f"/api/ai-queue/{ids[3]}/send")
            assert (refused.status_code, refused.json()["detail"]) == (429, "teacher_ai_limit")
            assert queue._find(ids[3])["state"] == "pending"                            # left waiting, not claimed
            assert len(app.state.photo.calls) == 3
            assert (await teacher.post("/api/math/photo", files=photo())).status_code == 429   # one allowance for all
    asyncio.run(check())


def test_a_failed_send_is_given_back():
    from app.math_photo import PhotoUnavailable
    app = make_app()

    class Broken(Solver):
        def solve(self, image, media_type):
            raise PhotoUnavailable("down", "provider_error", "")

    async def check():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            rid = (await student.post("/api/math/photo", files=photo())).json()["request"]["id"]
            app.state.photo = Broken()
            assert (await teacher.post(f"/api/ai-queue/{rid}/send")).json()["state"] == "failed"
            assert (await teacher.get("/api/me")).json()["ai_left"] == 3
    asyncio.run(check())


def test_a_developer_has_no_limit():
    app = make_app()
    app.state.auth.developers = frozenset({OTHER + "@test.invalid"})

    async def check():
        async with as_user(app, OTHER) as dev:
            assert (await dev.get("/api/me")).json()["ai_left"] is None
            for _ in range(5):
                assert (await dev.post("/api/math/photo", files=photo())).status_code == 200
    asyncio.run(check())


def test_the_teachers_own_answer_checks_count(answer_store):
    from test_answer_scans import begin, finish, request
    store = answer_store
    ids = [finish(store, begin(store, request(store, question=f"q{i}")))["attempt"]["id"] for i in range(4)]   # 4 answers
    app = make_app(store)
    app.state.auth.teachers = frozenset({OWNER + "@test.invalid"})   # OWNER has the teacher role and checks its own answers

    async def check():
        async with as_user(app, OWNER) as teacher:
            codes = []
            for aid in ids:
                r = await teacher.post(f"/api/math/answer-attempts/{aid}/grade")
                codes.append((r.status_code, r.json().get("detail")))
            assert codes[:3] == [(200, None)] * 3 and codes[3] == (429, "teacher_ai_limit")
            assert len(app.state.answer_grader.calls) == 3
    asyncio.run(check())
