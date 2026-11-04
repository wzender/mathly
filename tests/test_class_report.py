"""The class teacher's report: one of the students is the class's teacher and sees the others' progress and grades."""
import asyncio
import urllib.parse

import httpx

from app.answer_scans import ScanError
from app.main import create_app

TEACHER, STUDENT, NEWBIE, OUTSIDER = "t-id", "s-id", "n-id", "o-id"
EMAILS = {TEACHER: "teacher@x.test", STUDENT: "student@x.test", NEWBIE: "newbie@x.test", OUTSIDER: "out@x.test"}


class ReportAuth:
    url, key, secret = "https://test.invalid", "public-test", "server-test"
    teachers = developers = frozenset()

    def __init__(self):
        self.row = {"id": 3, "name": "ט׳1", "lessons": [], "teachers": ["teacher@x.test"],
                    "emails": ["newbie@x.test", "student@x.test", "teacher@x.test", "ghost@x.test"]}
        self.saved = []
        self.progress = {STUDENT: {"done": {"t1": "2026-11-01"}, "updated": 5, "comets": ["c1"],
                                   "slips": [{"at": "2026-11-01T10:00:00Z", "id": "t1", "q": 0, "m": "sign"}],
                                   "quizzes": [{"at": "2026-11-02", "n": 12, "right": 9, "ms": 600000, "units": ["t"],
                                                "weak": ["t1"]}],
                                   "uq": {"t": {"sitting": {"started": 1, "attempts": ["a"], "submitted": 2},
                                                "history": [{"at": "2026-11-03", "attempts": ["a"], "score": 85}]}}},
                         TEACHER: {"done": {"secret": 1}}}

    def user(self, token):
        return {"id": token, "email": EMAILS[token]} if token in EMAILS else None

    def classes(self, fresh=False):
        return [self.row]

    def access_for(self, _id, **kwargs):
        return None

    def user_ids(self, emails):
        return {e: i for i, e in EMAILS.items() if e in emails and i != NEWBIE} | (
            {"newbie@x.test": NEWBIE} if "newbie@x.test" in emails else {})

    def save_class(self, class_id, name, emails, nicknames, lessons, *, teachers=None):
        self.saved.append({"emails": emails, "teachers": teachers})

    def _admin(self, path, method="GET", body=None, prefer=""):
        table, _, query = path.partition("?")
        assert table == "/rest/v1/math_progress"
        ids = dict(urllib.parse.parse_qsl(query))["user_id"].removeprefix("in.(").removesuffix(")").split(",")
        return [{"user_id": i, "data": self.progress[i], "updated_at": "2026-11-03T00:00:00Z"}
                for i in ids if i in self.progress]


class Sittings:
    """The server's record of unit-quiz sittings (app/quiz_grades.py), as the database returns it."""
    configured = True

    def __init__(self, sittings=(), fail=False):
        self.sittings, self.fail, self.asked = list(sittings), fail, []

    def quiz(self, user_id, action, **data):
        self.asked.append((user_id, action, data))
        if self.fail:
            raise ScanError(503, "quiz_sittings_unavailable")
        return [s for s in self.sittings if s["user_id"] in data["users"]]


def attempt(score, state="completed", photo=True, verdict="correct"):
    return {"attempt_id": "a", "has_photo": photo, "grade_state": state, "score": score, "verdict": verdict}


def sitting(user, *attempts, sid="s1", at="2026-11-04T09:00:00Z"):
    return {"id": sid, "user_id": user, "unit_id": "t", "submitted_at": at, "time_up": False, "attempts": list(attempts)}


def client(app, user):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             headers={"Authorization": f"Bearer {user}"})


def test_teacher_sees_the_other_students():
    app = create_app(auth=ReportAuth())
    app.state.answers = Sittings()

    async def check():
        async with client(app, TEACHER) as c:
            r = await c.get("/api/classes/3/report")
            assert r.status_code == 200
            data = r.json()
            assert data["class"]["name"] == "ט׳1" and data["class"]["lessons"]
            students = {s["email"]: s for s in data["students"]}
            assert "teacher@x.test" not in students   # the teacher is not in their own report
            assert students["ghost@x.test"] == {"email": "ghost@x.test", "signed_in": False, "progress": None,
                                                "saved_at": None, "quiz_sittings": []}
            assert students["newbie@x.test"]["signed_in"] and students["newbie@x.test"]["progress"] is None
            p = students["student@x.test"]["progress"]
            assert p["done"] == {"t1": "2026-11-01"} and p["slips"][0]["m"] == "sign"
            assert p["quizzes"] == [{"at": "2026-11-02", "n": 12, "right": 9, "ms": 600000, "units": ["t"]}]
            assert p["uq"] == {"t": {"history": [{"at": "2026-11-03", "timeUp": None, "sid": None}], "going": False}}
            assert "comets" not in p
            assert (await c.get("/api/classes/99/report")).status_code == 404
            me = (await c.get("/api/me")).json()
            assert me["classes"][0]["teacher"] is True
        for other in (STUDENT, OUTSIDER):
            async with client(app, other) as c:
                assert (await c.get("/api/classes/3/report")).status_code == 403

    asyncio.run(check())


def test_unit_quiz_grades_are_the_servers_and_not_the_devices():
    auth = ReportAuth()   # the student's uploaded progress claims 85 for unit t
    app = create_app(auth=auth)
    app.state.answers = answers = Sittings([
        sitting(STUDENT, attempt(100), attempt(60), attempt(40), attempt(48), sid="s-done"),   # 25 + 15 + 10 + 12
        sitting(NEWBIE, attempt(100), attempt(None, state="grading", verdict=None), attempt(100), attempt(100),
                sid="s-open"),
        sitting(OUTSIDER, attempt(100), attempt(100), attempt(100), attempt(100), sid="s-other-class")])

    async def check():
        async with client(app, TEACHER) as c:
            data = (await c.get("/api/classes/3/report")).json()
            students = {s["email"]: s for s in data["students"]}
            done = students["student@x.test"]["quiz_sittings"]
            assert [(x["id"], x["grade"], x["open"]) for x in done] == [("s-done", 62, 0)]   # not 85
            waiting = students["newbie@x.test"]["quiz_sittings"]
            assert [(x["id"], x["grade"], x["open"]) for x in waiting] == [("s-open", None, 1)]
            assert students["ghost@x.test"]["quiz_sittings"] == []
            assert "score" not in str(students["student@x.test"]["progress"]["uq"])   # the device's number is not passed on
            assert answers.asked[0][:2] == (None, "report")
            assert OUTSIDER not in answers.asked[0][2]["users"] and "s-other-class" not in str(students)
    asyncio.run(check())


def test_without_the_servers_record_the_report_shows_no_quiz_grades():
    app = create_app(auth=ReportAuth())
    app.state.answers = Sittings(fail=True)

    async def check():
        async with client(app, TEACHER) as c:
            r = await c.get("/api/classes/3/report")
            assert r.status_code == 200
            assert all(s["quiz_sittings"] is None for s in r.json()["students"])
    asyncio.run(check())


def test_the_teacher_is_one_of_the_students():
    auth = ReportAuth()
    app = create_app(auth=auth)

    async def check():
        # a manager (TEACHER_EMAILS) saves the class
        auth.teachers = frozenset({"out@x.test"})
        async with client(app, OUTSIDER) as c:
            body = {"name": "ט׳1", "emails": ["a@x.test", "b@x.test"], "lessons": ["t"]}
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["c@x.test"]})).status_code == 400
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["a@x.test", "b@x.test"]})).status_code == 400
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["B@x.test"]})).status_code == 200
            assert (await c.put("/api/classes/3", json=body)).status_code == 200
            assert auth.saved == [{"emails": ["a@x.test", "b@x.test"], "teachers": ["b@x.test"]},
                                  {"emails": ["a@x.test", "b@x.test"], "teachers": []}]
            # a manager can open any class's report
            assert (await c.get("/api/classes/3/report")).status_code == 200

    asyncio.run(check())
