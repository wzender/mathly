"""The class teacher's report: one of the students is the class's teacher and sees the others' progress and grades."""
import asyncio
import urllib.parse

import httpx

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


def client(app, user):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             headers={"Authorization": f"Bearer {user}"})


def test_teacher_sees_the_other_students():
    app = create_app(auth=ReportAuth())

    async def check():
        async with client(app, TEACHER) as c:
            r = await c.get("/api/classes/3/report")
            assert r.status_code == 200
            data = r.json()
            assert data["class"]["name"] == "ט׳1" and data["class"]["lessons"]
            students = {s["email"]: s for s in data["students"]}
            assert "teacher@x.test" not in students   # the teacher is not in their own report
            assert students["ghost@x.test"] == {"email": "ghost@x.test", "signed_in": False, "progress": None,
                                                "saved_at": None}
            assert students["newbie@x.test"]["signed_in"] and students["newbie@x.test"]["progress"] is None
            p = students["student@x.test"]["progress"]
            assert p["done"] == {"t1": "2026-11-01"} and p["slips"][0]["m"] == "sign"
            assert p["quizzes"] == [{"at": "2026-11-02", "n": 12, "right": 9, "ms": 600000, "units": ["t"]}]
            assert p["uq"] == {"t": {"history": [{"at": "2026-11-03", "score": 85, "timeUp": None}], "going": False}}
            assert "comets" not in p
            assert (await c.get("/api/classes/99/report")).status_code == 404
            me = (await c.get("/api/me")).json()
            assert me["classes"][0]["teacher"] is True
        for other in (STUDENT, OUTSIDER):
            async with client(app, other) as c:
                assert (await c.get("/api/classes/3/report")).status_code == 403

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
