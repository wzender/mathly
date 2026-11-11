"""A lesson of a second subject, loaded as JSON, works through the whole path like a math lesson (add-subjects-and-worksheets 4.5):
practice and mastery, the lesson quiz, the review list, a real test with its exercise tests and simulation, and the grades."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from mathly2 import clock, content
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

MGR, DEV, TEACHER, KID = "mgr@school.test", "dev@school.test", "t@school.test", "kid@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))
MON = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def lesson_json():
    """Two skills of 12 questions each: choice 0 is always right, choice 1 always names the lesson's one mistake."""
    return {"name": "תאים", "mistakes": {"m": {"name": "בלבול בין איברים", "tip": "קראו שוב את התפקיד של כל איבר"}},
            "skills": [{"name": name, "questions": [{"question": f"{name}: שאלה {i}", "source": "sheet",
                                                     "choices": [{"text": "נכון", "correct": True}, {"text": f"לא {i}", "mistake": "m"}]}
                                                    for i in range(12)]} for name in ("מבנה התא", "קרום התא")]}


def world(monkeypatch):
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    app = create_app(Settings(developers=frozenset({DEV}), teachers=frozenset({TEACHER})), store=store)
    c = TestClient(app)
    moment = {"now": MON}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    c.set_time = lambda value: moment.update(now=value)
    sid = c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()["id"]
    made = c.post(f"/api/subjects/{sid}/lessons", json={"lesson": lesson_json()}, headers=auth(DEV)).json()
    store.save_lesson(made["id"], published=store.get_lesson(made["id"])["draft"])
    content.rebuild(app)
    klass = store.create_class("setup", "מדעים ט", teacher_email=TEACHER, subjects=[sid])
    store.add_member(klass["id"], KID)
    return c, store, sid, f"w{made['id']}", klass


def practise(c, skill_id, right=True):
    key = c.get(f"/api/skills/{skill_id}", headers=auth(KID)).json()["question"]["key"]
    got = c.post(f"/api/skills/{skill_id}/answer", json={"question_key": key, "choice": 0 if right else 1}, headers=auth(KID))
    assert got.status_code == 200, got.text
    return got.json()


def test_practice_mastery_quiz_review_tests_and_grades_on_a_second_subjects_lesson(monkeypatch):
    c, store, sid, unit, klass = world(monkeypatch)
    skill = f"{unit}_1"

    # practice: a wrong answer names the lesson's mistake and goes to review; three right ones on two days master the skill
    wrong = practise(c, skill, right=False)
    assert wrong["correct"] is False and wrong["mistake"]["name"] == "בלבול בין איברים"
    assert [r["skill_id"] for r in store.review_of(KID_ID)] == [skill]
    practise(c, skill)
    practise(c, skill)
    c.set_time(MON + timedelta(days=1))
    assert practise(c, skill)["state"] == "mastered"
    path = c.get(f"/api/path?subject={sid}", headers=auth(KID)).json()
    assert path["lessons"][0]["mastered"] == 1 and path["next"] == f"{unit}_2"

    # the lesson quiz: drawn from the lesson's two skills, graded, on the subject's grades
    quiz = c.post(f"/api/lessons/{unit}/quiz/start", headers=auth(KID)).json()
    assert len(quiz["questions"]) == 15 and {q["key"].split(":")[0] for q in quiz["questions"]} == {f"{unit}_1", f"{unit}_2"}
    for q in quiz["questions"]:
        c.put(f"/api/attempts/{quiz['id']}/answers", json={"key": q["key"], "choice": 0}, headers=auth(KID))
    done = c.post(f"/api/attempts/{quiz['id']}/submit", headers=auth(KID)).json()
    assert done["grade"] == 100
    grades = c.get(f"/api/grades?subject={sid}", headers=auth(KID)).json()
    assert [g["lesson"]["id"] for g in grades["quizzes"]] == [unit] and grades["quizzes"][0]["best"] == 100
    assert c.get("/api/grades", headers=auth(KID)).status_code == 404                          # the class does not study math

    # a real test in the subject: exercise test 1 and the simulation draw from its lesson and land on its grades
    day = (clock.school_day() + timedelta(days=3)).isoformat()
    test = c.post(f"/api/classes/{klass['id']}/tests", json={"date": day, "lessons": [unit], "questions": 6}, headers=auth(TEACHER)).json()
    assert test["subject_id"] == sid
    exercise = c.post(f"/api/tests/{test['id']}/exercise/1/start", headers=auth(KID))
    assert exercise.status_code == 200, exercise.text
    assert {q["key"].split(":")[0] for q in exercise.json()["questions"]} <= {f"{unit}_1", f"{unit}_2"}
    c.post(f"/api/attempts/{exercise.json()['id']}/submit", headers=auth(KID))
    c.set_time(MON + timedelta(days=3))                                                         # the day before the test: the simulation is open
    sim = c.post(f"/api/tests/{test['id']}/simulation/start", headers=auth(KID))
    assert sim.status_code == 200, sim.text
    c.post(f"/api/attempts/{sim.json()['id']}/submit", headers=auth(KID))
    grades = c.get(f"/api/grades?subject={sid}", headers=auth(KID)).json()
    assert len(grades["exercise_tests"]) == 1 and len(grades["simulations"]) == 1
    home = c.get(f"/api/home?subject={sid}", headers=auth(KID)).json()
    assert [t["id"] for t in home["tests"]] == [test["id"]]

    # the review list holds the subject's wrong answers, with the mistake's name when redone
    review = c.get("/api/review", headers=auth(KID))
    assert review.status_code == 200 and skill in str(review.json())
