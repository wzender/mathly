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


# ---- a class studies chosen subjects (3.4) ----

def test_a_new_class_studies_math_and_a_manager_adds_and_removes_a_subject_keeping_progress():
    c, store = world()
    sid = c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()["id"]
    made = c.post("/api/classes", json={"name": "ט'3", "students": "kid@school.test"}, headers=auth(MGR)).json()
    assert made["subjects"] == ["math"]
    body = {"name": "ט'3", "subjects": ["math", sid]}
    assert c.put(f"/api/classes/{made['id']}", json=body, headers=auth(MGR)).json()["subjects"] == ["math", sid]
    store.save_progress("u-kid", "w1_1", started_at="then", mastered_at="then")
    assert c.put(f"/api/classes/{made['id']}", json={"name": "ט'3", "subjects": ["math"]}, headers=auth(MGR)).json()["subjects"] == ["math"]
    assert store.get_progress("u-kid", "w1_1")["mastered_at"] == "then"                    # removing a subject keeps progress
    unchanged = c.put(f"/api/classes/{made['id']}", json={"name": "ט'3 א"}, headers=auth(MGR)).json()
    assert unchanged["subjects"] == ["math"]                                                   # an older client keeps the subjects


def test_a_class_needs_a_known_subject_and_at_least_one():
    c, _ = world()
    assert c.post("/api/classes", json={"name": "ט'5", "subjects": ["nowhere"]}, headers=auth(MGR)).status_code == 422
    assert c.post("/api/classes", json={"name": "ט'5", "subjects": []}, headers=auth(MGR)).status_code == 422


# ---- a student's lessons are the published lessons of their classes' subjects (3.5) ----

KID = "kid@school.test"


def published_science(c, store):
    sid = c.post("/api/subjects", json={"name": "מדעים", "icon": "⚗"}, headers=auth(MGR)).json()["id"]
    lesson = c.post(f"/api/subjects/{sid}/lessons", json={"lesson": science_lesson()}, headers=auth(DEV)).json()
    store.save_lesson(lesson["id"], published=store.get_lesson(lesson["id"])["draft"])
    from mathly2 import content
    content.rebuild(c.app)
    return sid, f"w{lesson['id']}"


def test_a_student_of_a_math_class_does_not_see_or_open_another_subjects_lesson():
    c, store = world()
    sid, unit = published_science(c, store)
    store.add_member(store.create_class("setup", "ט'1")["id"], KID)
    lessons = c.get("/api/lessons", headers=auth(KID)).json()
    assert lessons and all(l["subject_id"] == "math" for l in lessons)
    assert c.get(f"/api/skills/{unit}_1", headers=auth(KID)).status_code == 404
    assert c.get(f"/api/lessons/{unit}/quiz", headers=auth(KID)).status_code == 404


def test_two_classes_with_two_subjects_give_a_student_both():
    c, store = world()
    sid, unit = published_science(c, store)
    store.add_member(store.create_class("setup", "ט'1")["id"], KID)
    store.add_member(store.create_class("setup", "מדעים ט", subjects=[sid])["id"], KID)
    lessons = c.get("/api/lessons", headers=auth(KID)).json()
    assert {l["subject_id"] for l in lessons} == {"math", sid} and lessons[-1]["id"] == unit
    assert c.get(f"/api/skills/{unit}_1", headers=auth(KID)).status_code == 200


def test_a_student_in_no_class_has_no_lessons_and_a_teacher_has_every_subject():
    c, store = world()
    sid, unit = published_science(c, store)
    assert c.get("/api/lessons", headers=auth(KID)).status_code == 403              # not in a class: asked to talk to the teacher
    assert unit in [l["id"] for l in c.get("/api/lessons", headers=auth(TEACHER)).json()]


# ---- per-subject student screens (4.1, 4.2) ----

def two_subject_student(c, store):
    sid, unit = published_science(c, store)
    store.add_member(store.create_class("setup", "ט'1")["id"], KID)
    store.add_member(store.create_class("setup", "מדעים ט", subjects=[sid])["id"], KID)
    return sid, unit


def test_the_subject_cards_are_the_students_subjects_math_first_each_counting_its_own_skills():
    c, store = world()
    sid, unit = two_subject_student(c, store)
    cards = c.get("/api/my-subjects", headers=auth(KID)).json()
    assert [s["id"] for s in cards] == ["math", sid]
    assert cards[1] == {"id": sid, "name": "מדעים", "icon": "⚗", "total": 1, "mastered": 0}
    assert cards[0]["total"] == sum(len(l["skills"]) for l in c.app.state.bank.lessons_with_skills() if l["subject_id"] == "math")


def test_the_path_home_grades_and_collection_are_per_subject_and_another_subjects_lessons_are_absent():
    c, store = world()
    sid, unit = two_subject_student(c, store)
    science = c.get(f"/api/path?subject={sid}", headers=auth(KID)).json()
    assert [l["id"] for l in science["lessons"]] == [unit] and science["next"] == f"{unit}_1"
    math = c.get("/api/path", headers=auth(KID)).json()
    assert unit not in [l["id"] for l in math["lessons"]] and math["next"] != f"{unit}_1"
    assert c.get(f"/api/home?subject={sid}", headers=auth(KID)).json()["next_skill"]["id"] == f"{unit}_1"
    assert c.get(f"/api/grades?subject={sid}", headers=auth(KID)).status_code == 200
    assert c.get(f"/api/collection?subject={sid}", headers=auth(KID)).json() == {"skills": [], "lessons": []}
    assert c.get("/api/path?subject=nowhere", headers=auth(KID)).status_code == 404


def test_the_owl_stays_in_its_subject():
    c, store = world()
    sid, unit = two_subject_student(c, store)
    key = c.get(f"/api/skills/{unit}_1", headers=auth(KID)).json()["question"]["key"]
    c.post(f"/api/skills/{unit}_1/answer", json={"question_key": key, "choice": 1}, headers=auth(KID))     # last answer: in science
    math = c.get("/api/path", headers=auth(KID)).json()
    assert math["next"].startswith("w") is False                                                     # math's owl is on a math skill


def test_a_student_cannot_open_a_subject_their_classes_do_not_study():
    c, store = world()
    sid, unit = published_science(c, store)
    store.add_member(store.create_class("setup", "ט'1")["id"], KID)
    assert [s["id"] for s in c.get("/api/my-subjects", headers=auth(KID)).json()] == ["math"]
    assert c.get(f"/api/path?subject={sid}", headers=auth(KID)).status_code == 404
