"""The class teacher's report: one of the students is the class's teacher and sees the others' progress and grades."""
import asyncio
import urllib.parse

import httpx

from app.answer_scans import ScanError
from app.auth import AuthUnavailable
from app.main import create_app

TEACHER, STUDENT, NEWBIE, OUTSIDER = "t-id", "s-id", "n-id", "o-id"
EMAILS = {TEACHER: "teacher@x.test", STUDENT: "student@x.test", NEWBIE: "newbie@x.test", OUTSIDER: "out@x.test"}


class ReportAuth:
    url, key, secret = "https://test.invalid", "public-test", "server-test"
    teachers = developers = frozenset()

    def __init__(self):
        self.row = {"id": 3, "name": "ט׳1", "lessons": [], "teachers": ["teacher@x.test"],
                    "emails": ["newbie@x.test", "student@x.test", "teacher@x.test", "ghost@x.test"],
                    "nicknames": {"newbie@x.test": "נועה ל."}}
        self.saved = []
        self.progress = {STUDENT: {"done": {"t1": "2026-11-01"}, "updated": 5, "comets": ["c1"],
                                   "seen": {"t1": "2026-11-01T10:00:00Z"}, "tries": {"t1": 4, "t2": 1}, "secret_extra": 1,
                                   "examples": {"t1": {"n": 3, "last": "2026-11-02T10:00:00Z"}},
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

    NAMES = {STUDENT: "Sam Student"}   # Google names; the others have none

    def user_accounts(self, emails):
        return {e: {"id": i, "name": self.NAMES.get(i, "")} for i, e in EMAILS.items() if e in emails}

    def save_class(self, class_id, name, emails, nicknames, lessons, *, teachers=None):
        self.saved.append({"emails": emails, "teachers": teachers})

    def _admin(self, path, method="GET", body=None, prefer=""):
        table, _, query = path.partition("?")
        if table != "/rest/v1/math_progress":
            raise AuthUnavailable("supabase answered 404: no other tables here")   # e.g. the assignments table: not set up
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

    def review(self, user_id, action, **data):   # the students' open requests to look again
        assert action == "requests"
        if self.fail:
            raise ScanError(503, "review_unavailable")
        return [r for r in getattr(self, "requests", []) if r["user_id"] in data["users"]]


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
                                                "saved_at": None, "quiz_sittings": [], "name": None, "review_requests": [],
                                                "worksheet_submissions": None}   # no worksheet tables here
            assert students["newbie@x.test"]["signed_in"] and students["newbie@x.test"]["progress"] is None
            p = students["student@x.test"]["progress"]
            assert p["done"] == {"t1": "2026-11-01"} and p["slips"][0]["m"] == "sign"
            assert p["quizzes"] == [{"at": "2026-11-02", "n": 12, "right": 9, "ms": 600000, "units": ["t"]}]
            assert p["uq"] == {"t": {"history": [{"at": "2026-11-03", "timeUp": None, "sid": None}], "going": False}}
            assert p["seen"] == {"t1": "2026-11-01T10:00:00Z"} and p["tries"] == {"t1": 4, "t2": 1}
            assert p["examples"] == {"t1": {"n": 3, "last": "2026-11-02T10:00:00Z"}}   # the worked examples the student opened
            assert "comets" not in p and "secret_extra" not in p
            assert (await c.get("/api/classes/99/report")).status_code == 404
            me = (await c.get("/api/me")).json()
            assert me["classes"][0]["teacher"] is True
        for other in (STUDENT, OUTSIDER):
            async with client(app, other) as c:
                assert (await c.get("/api/classes/3/report")).status_code == 403

    asyncio.run(check())


def test_students_are_named_by_nickname_then_google_name_then_nothing():
    app = create_app(auth=ReportAuth())
    app.state.answers = Sittings()

    async def check():
        async with client(app, TEACHER) as c:
            students = {s["email"]: s for s in (await c.get("/api/classes/3/report")).json()["students"]}
            assert students["newbie@x.test"]["name"] == "נועה ל."      # the class's nickname
            assert students["student@x.test"]["name"] == "Sam Student"  # else the Google name
            assert students["ghost@x.test"]["name"] is None             # else the page uses the email's start
    asyncio.run(check())


def test_google_names_come_from_the_admin_user_list():
    from app.auth import SupabaseAuth
    auth = SupabaseAuth("https://x.invalid", "key", secret="secret")
    users = [{"id": "u1", "email": "A@x.test", "user_metadata": {"full_name": " Noa   Levi "}},
             {"id": "u2", "email": "b@x.test", "user_metadata": {"name": "Ben"}},
             {"id": "u3", "email": "c@x.test"}, {"id": "u4", "email": "other@x.test"}]
    auth._admin = lambda path, *a, **k: {"users": users}
    got = auth.user_accounts(["a@x.test", "B@x.test", "c@x.test", "nobody@x.test"])
    assert got == {"a@x.test": {"id": "u1", "name": "Noa Levi"}, "b@x.test": {"id": "u2", "name": "Ben"},
                   "c@x.test": {"id": "u3", "name": ""}}
    assert auth.user_ids(["a@x.test"]) == {"a@x.test": "u1"}


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


def test_the_teacher_is_free_text_and_never_a_student():
    auth = ReportAuth()
    app = create_app(auth=auth)

    async def check():
        # a manager (TEACHER_EMAILS) saves the class
        auth.developers = frozenset({"out@x.test"})
        async with client(app, OUTSIDER) as c:
            body = {"name": "ט׳1", "emails": ["a@x.test", "b@x.test"], "lessons": ["t"]}
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["a@x.test"]})).status_code == 400   # a student
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["B@x.test"]})).status_code == 400
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["c@x.test", "d@x.test"]})).status_code == 400
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["nope"]})).status_code == 400
            assert (await c.put("/api/classes/3", json={**body, "teachers": ["C@x.test"]})).status_code == 200
            assert (await c.put("/api/classes/3", json=body)).status_code == 200
            assert auth.saved == [{"emails": ["a@x.test", "b@x.test"], "teachers": ["c@x.test"]},
                                  {"emails": ["a@x.test", "b@x.test"], "teachers": []}]
            # a manager can open any class's report
            assert (await c.get("/api/classes/3/report")).status_code == 200

    asyncio.run(check())


def test_progress_parts_that_are_not_objects_are_dropped():
    from app.class_report import report_part
    part = report_part({"seen": "yesterday", "tries": [1, 2], "days": None, "examples": "many", "done": {"a": 1}})
    assert part["seen"] == {} and part["tries"] == {} and part["days"] == {} and part["examples"] == {} and part["done"] == {"a": 1}


def test_the_report_lists_each_students_open_requests_to_look_again():
    app = create_app(auth=ReportAuth())
    app.state.answers = answers = Sittings()
    answers.requests = [
        {"attempt_id": "a1", "user_id": STUDENT, "message": "כתבתי x=4", "question": "בוחן: שאלה 2", "created_at": "2026-11-04T10:00:00Z"},
        {"attempt_id": "a2", "user_id": OUTSIDER, "message": "של כיתה אחרת", "question": "q", "created_at": "2026-11-04T10:00:00Z"}]

    async def check():
        async with client(app, TEACHER) as c:
            students = {s["email"]: s for s in (await c.get("/api/classes/3/report")).json()["students"]}
            assert students["student@x.test"]["review_requests"] == [
                {"attempt_id": "a1", "message": "כתבתי x=4", "question": "בוחן: שאלה 2", "created_at": "2026-11-04T10:00:00Z"}]
            assert students["newbie@x.test"]["review_requests"] == [] and "של כיתה אחרת" not in str(students)
        answers.fail = True   # unreadable: the report still opens, without them
        async with client(app, TEACHER) as c:
            r = await c.get("/api/classes/3/report")
            assert r.status_code == 200 and all(s["review_requests"] == [] for s in r.json()["students"])
    asyncio.run(check())


def test_the_report_carries_the_classs_assignments_for_its_teacher():
    from test_assignments import GOOD, MemoryAssignments
    store = MemoryAssignments()
    app = create_app(auth=ReportAuth())
    app.state.answers, app.state.assignments = Sittings(), store
    store.add({**GOOD, "class_id": 3, "created_by_email": "teacher@x.test"})
    store.add({**GOOD, "class_id": 99, "title": "של כיתה אחרת", "created_by_email": "x@x.test"})

    async def check():
        async with client(app, TEACHER) as c:
            data = (await c.get("/api/classes/3/report")).json()
            assert [(a["title"], a["class_id"], a["created_by_email"]) for a in data["assignments"]] == [(GOOD["title"], 3, "teacher@x.test")]
            assert data["assignments"][0]["items"] == GOOD["items"]
        store.fail = True
        async with client(app, TEACHER) as c:   # the table is not there: the report opens, without assignments
            r = await c.get("/api/classes/3/report")
            assert r.status_code == 200 and r.json()["assignments"] is None
    asyncio.run(check())


def test_the_report_says_which_sittings_are_final_and_shows_their_grade_to_the_teacher():
    """A final sitting's grade is the teacher's to see before release (the student's view waits for it)."""
    app = create_app(auth=ReportAuth())
    app.state.answers = Sittings([
        {**sitting(STUDENT, attempt(100), attempt(100), attempt(100), attempt(40), sid="s-final"), "mode": "final",
         "window_id": "w1", "started_at": "2026-11-04T08:00:00Z"},
        sitting(STUDENT, attempt(100), attempt(100), attempt(100), attempt(100), sid="s-practice", at="2026-11-05T09:00:00Z")])

    async def check():
        async with client(app, TEACHER) as c:
            students = {s["email"]: s for s in (await c.get("/api/classes/3/report")).json()["students"]}
            mine = {x["id"]: x for x in students["student@x.test"]["quiz_sittings"]}
            assert (mine["s-final"]["mode"], mine["s-final"]["grade"], mine["s-final"]["window_id"]) == ("final", 85, "w1")
            assert (mine["s-practice"]["mode"], mine["s-practice"]["grade"]) == ("practice", 100)
    asyncio.run(check())


def test_the_class_teacher_says_which_units_an_exam_covers():
    auth = ReportAuth()
    auth.row = {**auth.row, "lessons": ["t", "k"], "exams": [{"subject": "מתמטיקה", "date": "2026-11-18"},
                                                             {"subject": "מדעים", "date": "2026-11-20"}]}
    saved = []
    auth.save_class_exams = lambda class_id, exams: saved.append((class_id, exams))
    app = create_app(auth=auth)
    app.state.answers = Sittings()
    url = "/api/classes/3/exams/topics"
    body = {"subject": "מתמטיקה", "date": "2026-11-18", "units": ["k", "t"], "note": "פרק 3 עד עמוד 80"}

    async def check():
        async with client(app, TEACHER) as c, client(app, STUDENT) as student:
            assert (await student.put(url, json=body)).status_code == 403
            assert (await c.put(url, json={**body, "units": ["g"]})).status_code == 400            # not a class unit
            assert (await c.put(url, json={**body, "note": "א" * 301})).status_code == 400
            assert (await c.put(url, json={**body, "date": "2026-12-01"})).status_code == 404
            r = await c.put(url, json=body)
            assert r.status_code == 200 and r.json()["units"] == ["t", "k"] and r.json()["note"] == "פרק 3 עד עמוד 80"
            (class_id, exams), = saved
            assert class_id == 3 and exams[0]["units"] == ["t", "k"] and "units" not in exams[1]   # the other exam is as it was
            cleared = await c.put(url, json={**body, "units": [], "note": ""})
            assert cleared.json()["units"] == []   # an exam without units works as before
    asyncio.run(check())


def test_the_report_carries_the_classs_exams_for_readiness():
    auth = ReportAuth()
    auth.row = {**auth.row, "lessons": ["t"], "exams": [{"subject": "מתמטיקה", "date": "2026-11-18", "units": ["t"]}, "junk"]}
    app = create_app(auth=auth)
    app.state.answers = Sittings()

    async def check():
        async with client(app, TEACHER) as c:
            data = (await c.get("/api/classes/3/report")).json()
            assert data["class"]["exams"] == [{"subject": "מתמטיקה", "date": "2026-11-18", "units": ["t"]}]
    asyncio.run(check())


def test_each_quiz_question_in_the_report_names_its_skills_and_points():
    app = create_app(auth=ReportAuth())
    app.state.answers = Sittings([sitting(STUDENT, attempt(100), attempt(40), attempt(100), attempt(100))])

    async def check():
        async with client(app, TEACHER) as c:
            students = {s["email"]: s for s in (await c.get("/api/classes/3/report")).json()["students"]}
            q = students["student@x.test"]["quiz_sittings"][0]["questions"][1]
            assert (q["points"], q["earned"], q["skills"]) == (25, 10, ["t_ext_eq"])   # 15 points lost on t_ext_eq
    asyncio.run(check())


def test_the_class_teacher_adds_and_removes_exams_on_the_classs_table():
    auth = ReportAuth()
    auth.row = {**auth.row, "lessons": ["t", "k"], "exams": [{"subject": "מתמטיקה", "date": "2026-11-18"}]}

    def save(class_id, exams):
        auth.row = {**auth.row, "exams": exams}
    auth.save_class_exams = save
    app = create_app(auth=auth)
    app.state.answers = Sittings()

    async def check():
        async with client(app, TEACHER) as c, client(app, STUDENT) as student:
            new = {"subject": "מתמטיקה", "date": "2026-12-02", "units": ["k"], "note": "דלתון"}
            assert (await student.post("/api/classes/3/exams", json=new)).status_code == 403
            for bad in ({**new, "date": "soon"}, {**new, "subject": ""}, {**new, "units": ["g"]}):
                assert (await c.post("/api/classes/3/exams", json=bad)).status_code == 400, bad
            made = await c.post("/api/classes/3/exams", json=new)
            assert made.status_code == 201 and made.json() == new
            assert (await c.post("/api/classes/3/exams", json=new)).status_code == 409   # the same exam twice
            assert [e["date"] for e in auth.row["exams"]] == ["2026-11-18", "2026-12-02"]   # by date
            gone = await c.delete("/api/classes/3/exams", params={"subject": "מתמטיקה", "date": "2026-11-18"})
            assert gone.status_code == 200 and [e["date"] for e in auth.row["exams"]] == ["2026-12-02"]
            assert (await c.delete("/api/classes/3/exams", params={"subject": "x", "date": "2026-01-01"})).status_code == 404
    asyncio.run(check())
