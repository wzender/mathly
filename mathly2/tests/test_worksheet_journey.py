"""The whole road from a worksheet to a student (add-subjects-and-worksheets 8.1), with a fake AI: a manager uploads a worksheet for a
new subject, fixes the draft, publishes it and gives the subject to a class; a student practises, masters a skill and takes the
quiz; the class's teacher sets a test in the new subject."""
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from PIL import Image

from mathly2 import clock, worksheets
from mathly2.ai import FakeAI
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

MGR, TEACHER, KID = "mgr@school.test", "t@school.test", "kid@school.test"
MON = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)


def auth(email, kind=None):
    return {"Authorization": f"Bearer dev:{email}", **({"Content-Type": kind} if kind else {})}


def test_from_a_worksheet_to_a_student_and_a_test(monkeypatch):
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    fake = FakeAI()
    app = create_app(Settings(teachers=frozenset({TEACHER})), store=store, ai_client=fake)
    app.state.run_worksheet = worksheets.run
    c = TestClient(app)
    moment = {"now": MON}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])

    # the manager: upload, draft, fix, publish
    lesson = c.post("/api/worksheets", json={"new_subject": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()
    sid, lid = lesson["subject_id"], lesson["id"]
    sheet = io.BytesIO()
    Image.new("RGB", (600, 800), (255, 255, 255)).save(sheet, "PDF")
    assert c.post(f"/api/worksheets/{lid}/files", content=sheet.getvalue(), headers=auth(MGR, "application/pdf")).status_code == 201
    c.post(f"/api/worksheets/{lid}/draft", headers=auth(MGR))
    draft = c.get(f"/api/subjects/lessons/{lid}", headers=auth(MGR)).json()["draft"]
    draft["name"] = "התא החי"
    draft["skills"][0]["questions"][0]["question"] = "מהו הגרעין?"
    assert c.put(f"/api/subjects/lessons/{lid}/draft", json={"lesson": draft}, headers=auth(MGR)).status_code == 200
    assert c.post(f"/api/subjects/lessons/{lid}/publish", headers=auth(MGR)).status_code == 200

    # the class studies the new subject
    made = c.post("/api/classes", json={"name": "ט'3", "teacher_email": TEACHER, "students": KID, "subjects": ["math", sid]}, headers=auth(MGR))
    assert made.status_code == 201
    klass = made.json()

    # the student: a card, practice to mastery, the quiz
    cards = c.get("/api/my-subjects", headers=auth(KID)).json()
    assert [s["name"] for s in cards] == ["מתמטיקה", "מדעים"]
    path = c.get(f"/api/path?subject={sid}", headers=auth(KID)).json()
    assert [l["name"] for l in path["lessons"]] == ["התא החי"]
    skill = path["next"]
    for day, answers in ((0, 2), (1, 1)):
        moment["now"] = MON + timedelta(days=day)
        for _ in range(answers):
            key = c.get(f"/api/skills/{skill}", headers=auth(KID)).json()["question"]["key"]
            got = c.post(f"/api/skills/{skill}/answer", json={"question_key": key, "choice": 0}, headers=auth(KID)).json()
    assert got["state"] == "mastered"
    quiz = c.post(f"/api/lessons/w{lid}/quiz/start", headers=auth(KID)).json()
    for q in quiz["questions"]:
        c.put(f"/api/attempts/{quiz['id']}/answers", json={"key": q["key"], "choice": 0}, headers=auth(KID))
    assert c.post(f"/api/attempts/{quiz['id']}/submit", headers=auth(KID)).json()["grade"] == 100
    assert c.get(f"/api/grades?subject={sid}", headers=auth(KID)).json()["quizzes"][0]["best"] == 100

    # the teacher: a test in the new subject reaches the student's science home
    test = c.post(f"/api/classes/{klass['id']}/tests", json={"date": (clock.school_day() + timedelta(days=14)).isoformat(), "lessons": [f"w{lid}"]},
                  headers=auth(TEACHER))
    assert test.status_code == 201 and test.json()["subject_id"] == sid
    assert [t["id"] for t in c.get(f"/api/home?subject={sid}", headers=auth(KID)).json()["tests"]] == [test.json()["id"]]
    assert c.get("/api/home", headers=auth(KID)).json()["tests"] == []
    assert [r["feature"] for r in store.ai_usage_rows()] == ["worksheet"]
