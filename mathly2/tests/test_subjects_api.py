"""Subjects and lessons loaded as JSON (add-subjects-and-worksheets 3.1, 3.2)."""
from fastapi.testclient import TestClient

from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

MGR, DEV, TEACHER = "mgr@school.test", "dev@school.test", "t@school.test"


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def world():
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    app = create_app(Settings(developers=frozenset({DEV}), teachers=frozenset({TEACHER})), store=store)
    return TestClient(app), store


def science_lesson(name="תאים", per_skill=5):
    return {"name": name, "mistakes": {"m": {"name": "בלבול", "tip": "קראו שוב"}},
            "skills": [{"name": "מבנה התא", "questions": [{"question": f"שאלה {i}", "source": "sheet",
                        "choices": [{"text": "נכון", "correct": True}, {"text": "לא", "mistake": "m"}]} for i in range(per_skill)]}]}


def test_a_manager_creates_renames_and_lists_subjects_with_math_fixed_first():
    c, _ = world()
    made = c.post("/api/subjects", json={"name": "  מדעים ", "icon": "⚗"}, headers=auth(MGR))
    assert made.status_code == 201 and made.json()["name"] == "מדעים"
    sid = made.json()["id"]
    listed = c.get("/api/subjects", headers=auth(MGR)).json()["subjects"]
    assert [s["name"] for s in listed] == ["מתמטיקה", "מדעים"] and listed[0]["fixed"] is True and listed[0]["file_lessons"]
    assert c.put(f"/api/subjects/{sid}", json={"name": "ביולוגיה", "icon": "🧬"}, headers=auth(MGR)).json() == {"id": sid, "name": "ביולוגיה", "icon": "🧬"}
    assert [s["name"] for s in c.app.state.bank.subjects] == ["מתמטיקה", "ביולוגיה"]                 # the served bank knows it at once


def test_subject_names_are_unique_ignoring_case_and_need_a_listed_icon():
    c, _ = world()
    assert c.post("/api/subjects", json={"name": "Science", "icon": "⚗"}, headers=auth(MGR)).status_code == 201
    assert c.post("/api/subjects", json={"name": "science", "icon": "⚗"}, headers=auth(MGR)).status_code == 409
    assert c.post("/api/subjects", json={"name": "Art", "icon": "X"}, headers=auth(MGR)).status_code == 422
    assert c.post("/api/subjects", json={"name": " ", "icon": "⚗"}, headers=auth(MGR)).status_code == 422


def test_a_teacher_cannot_create_a_subject_and_math_cannot_be_renamed_or_deleted():
    c, _ = world()
    assert c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(TEACHER)).status_code == 403
    assert c.put("/api/subjects/math", json={"name": "חשבון"}, headers=auth(MGR)).status_code == 422
    assert c.delete("/api/subjects/math", headers=auth(MGR)).status_code == 422


def test_a_subject_with_a_published_lesson_cannot_be_deleted_but_an_empty_one_can():
    c, store = world()
    sid = c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()["id"]
    lesson = c.post(f"/api/subjects/{sid}/lessons", json={"lesson": science_lesson()}, headers=auth(DEV)).json()
    store.save_lesson(lesson["id"], published=store.get_lesson(lesson["id"])["draft"])
    refused = c.delete(f"/api/subjects/{sid}", headers=auth(MGR))
    assert refused.status_code == 409 and "מבטלים את פרסומם" in refused.json()["detail"]
    store.save_lesson(lesson["id"], published=None)
    assert c.delete(f"/api/subjects/{sid}", headers=auth(MGR)).status_code == 204
    assert store.lessons_of(sid) == [] and [s["id"] for s in store.subjects()] == ["math"]


def test_reordering_a_subjects_lessons_changes_the_served_order():
    c, store = world()
    sid = c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()["id"]
    a = c.post(f"/api/subjects/{sid}/lessons", json={"lesson": science_lesson("א")}, headers=auth(DEV)).json()["id"]
    b = c.post(f"/api/subjects/{sid}/lessons", json={"lesson": science_lesson("ב")}, headers=auth(DEV)).json()["id"]
    for lesson_id in (a, b):
        store.save_lesson(lesson_id, published=store.get_lesson(lesson_id)["draft"])
    got = c.put(f"/api/subjects/{sid}/order", json={"lessons": [b, a]}, headers=auth(MGR))
    assert [l["id"] for l in got.json()["lessons"]] == [b, a]
    assert [u["name"] for u in c.app.state.bank.lessons_of_subject(sid)] == ["ב", "א"]
    assert c.put(f"/api/subjects/{sid}/order", json={"lessons": [a]}, headers=auth(MGR)).status_code == 422


def test_a_developer_loads_a_lesson_as_json_and_it_is_a_draft_with_ids_of_the_lesson():
    c, store = world()
    sid = c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()["id"]
    got = c.post(f"/api/subjects/{sid}/lessons", json={"lesson": science_lesson()}, headers=auth(DEV))
    assert got.status_code == 201 and got.json()["published"] is False
    draft = got.json()["draft"]
    n = got.json()["id"]
    assert draft["skills"][0]["id"] == f"w{n}_1" and list(draft["mistakes"]) == [f"w{n}_m1"]
    assert c.app.state.bank.lessons_of_subject(sid) == []                                     # a draft never reaches students
    assert c.post(f"/api/subjects/{sid}/lessons", json={"lesson": science_lesson()}, headers=auth(MGR)).status_code == 403


def test_a_malformed_lesson_is_refused_with_the_checks_messages_and_nothing_is_kept():
    c, store = world()
    sid = c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()["id"]
    bad = science_lesson()
    bad["skills"][0]["questions"][0]["choices"][1]["correct"] = True
    got = c.post(f"/api/subjects/{sid}/lessons", json={"lesson": bad}, headers=auth(DEV))
    assert got.status_code == 422 and any("2 correct choices" in p for p in got.json()["detail"]["problems"])
    assert store.lessons_of(sid) == []
