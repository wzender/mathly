import pytest
from fastapi.testclient import TestClient

from mathly2.classes import parse_emails
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

MGR, T1, T2, DEV = "mgr@school.test", "t1@school.test", "t2@school.test", "dev@school.test"


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


@pytest.fixture
def world():
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    client = TestClient(create_app(Settings(teachers=frozenset({T1, T2}), developers=frozenset({DEV})), store=store))
    return client, store


def body(name="ט'3", **kw):
    return {"name": name, "lessons": kw.pop("lessons", ["t", "t2"]), **kw}


def make(client, who=MGR, **kw):
    return client.post("/api/classes", json=body(**kw), headers=auth(who))


def test_parse_emails_handles_pasted_lists():
    valid, invalid = parse_emails(" A@x.test, b@x.test;\nc@x.test  a@x.test not-an-email ")
    assert valid == ["a@x.test", "b@x.test", "c@x.test"] and invalid == ["not-an-email"]


# ---- the manager makes classes (spec: Manager creates classes)

def test_a_manager_creates_a_class_with_lessons_teacher_and_students(world):
    client, _ = world
    created = make(client, teacher_email=T1, students="s1@school.test\ns2@school.test not-an-email")
    assert created.status_code == 201
    row = created.json()
    assert row["name"] == "ט'3" and row["lessons"] == ["t", "t2"] and row["teacher_email"] == T1
    assert row["ai_enabled"] is False and row["ai_daily_checks"] == 150
    assert row["students"] == 2 and row["student_emails"] == ["s1@school.test", "s2@school.test"] and row["invalid"] == ["not-an-email"]
    assert [c["name"] for c in client.get("/api/classes", headers=auth(MGR)).json()] == ["ט'3"]


def test_a_developer_can_manage_classes_too(world):
    client, _ = world
    assert make(client, who=DEV).status_code == 201


def test_a_teacher_a_student_and_a_stranger_cannot_create_classes(world):
    client, _ = world
    assert make(client, who=T1).status_code == 403
    assert make(client, who="kid@school.test").status_code == 403
    assert client.post("/api/classes", json=body()).status_code == 401
    assert client.get("/api/classes", headers=auth(T1)).status_code == 403


def test_class_name_is_trimmed_checked_and_unique_ignoring_case(world):
    client, _ = world
    assert make(client, name="  ח'  1 ").json()["name"] == "ח' 1"
    assert make(client, name="ח' 1").status_code == 409
    assert make(client, name="   ").status_code == 422
    assert make(client, name="x" * 81).status_code == 422
    assert make(client, name="x" * 80).status_code == 201


def test_a_class_needs_at_least_one_known_lesson(world):
    client, _ = world
    assert make(client, lessons=[]).status_code == 422
    assert make(client, lessons=["nope"]).status_code == 422
    assert make(client, lessons=["t", "nope"]).status_code == 422
    assert make(client, name="B", lessons=["t", "t"]).json()["lessons"] == ["t"]      # repeats collapse


def test_the_teacher_must_be_an_email_and_not_also_a_student(world):
    client, _ = world
    assert make(client, teacher_email="not-an-email").status_code == 422
    clash = make(client, teacher_email=T1, students=f"s@school.test {T1}")
    assert clash.status_code == 422 and "תלמיד" in clash.json()["detail"]
    assert client.get("/api/classes", headers=auth(MGR)).json() == []                 # nothing was saved


def test_the_ai_budget_is_limited(world):
    client, _ = world
    assert make(client, ai_daily_checks=-1).status_code == 422
    assert make(client, name="B", ai_daily_checks=10001).status_code == 422
    assert make(client, name="C", ai_daily_checks=40, ai_enabled=True).json()["ai_enabled"] is True


def test_the_manager_can_list_the_lessons_to_choose_from(world):
    client, _ = world
    lessons = client.get("/api/classes/lessons", headers=auth(MGR)).json()
    assert len(lessons) == 24 and set(lessons[0]) == {"id", "name", "skills"} and lessons[0]["skills"] > 0
    assert client.get("/api/classes/lessons", headers=auth(T1)).status_code == 403


# ---- editing and deleting (spec: Editing and deleting a class)

def test_a_manager_edits_everything_and_the_roster_follows(world):
    client, store = world
    cid = make(client, teacher_email=T1, students="a@school.test b@school.test").json()["id"]
    edited = client.put(f"/api/classes/{cid}", json=body("ט'4", lessons=["k"], teacher_email=T2, students="b@school.test c@school.test",
                                                          ai_enabled=True, ai_daily_checks=60), headers=auth(MGR)).json()
    assert (edited["name"], edited["lessons"], edited["teacher_email"], edited["ai_enabled"], edited["ai_daily_checks"]) == ("ט'4", ["k"], T2, True, 60)
    assert edited["student_emails"] == ["b@school.test", "c@school.test"]


def test_leaving_the_students_out_of_an_edit_keeps_the_roster(world):
    client, _ = world
    cid = make(client, students="a@school.test").json()["id"]
    kept = client.put(f"/api/classes/{cid}", json=body("ט'3"), headers=auth(MGR)).json()
    assert kept["student_emails"] == ["a@school.test"]


def test_removing_a_student_through_an_edit_keeps_their_progress(world):
    client, store = world
    cid = make(client, students="a@school.test").json()["id"]
    store.save_progress("u-a", "t_ext", started_at="then")
    client.put(f"/api/classes/{cid}", json=body(students=""), headers=auth(MGR))
    assert client.get(f"/api/classes/{cid}", headers=auth(MGR)).json()["students"] == 0
    assert store.get_progress("u-a", "t_ext")["started_at"] == "then"


def test_editing_cannot_clash_with_another_class_or_make_a_student_the_teacher(world):
    client, _ = world
    make(client, name="A")
    cid = make(client, name="B", students="s@school.test").json()["id"]
    assert client.put(f"/api/classes/{cid}", json=body("a"), headers=auth(MGR)).status_code == 409
    assert client.put(f"/api/classes/{cid}", json=body("B", teacher_email="s@school.test"), headers=auth(MGR)).status_code == 422
    assert client.put("/api/classes/999", json=body("Z"), headers=auth(MGR)).status_code == 404


def test_deleting_a_class_asks_nothing_of_the_students_progress(world):
    client, store = world
    cid = make(client, students="a@school.test").json()["id"]
    store.save_progress("u-a", "t_ext", started_at="then")
    assert client.delete(f"/api/classes/{cid}", headers=auth(MGR)).status_code == 204
    assert client.delete(f"/api/classes/{cid}", headers=auth(MGR)).status_code == 404
    assert client.get("/api/classes", headers=auth(MGR)).json() == []
    assert store.get_progress("u-a", "t_ext")["started_at"] == "then"


# ---- the roster (spec: Teacher adds students by email)

def test_the_classes_teacher_adds_a_list_of_students(world):
    client, _ = world
    cid = make(client, teacher_email=T1).json()["id"]
    emails = "\n".join(f"s{i}@school.test" for i in range(25)) + "\ndana@"
    result = client.post(f"/api/classes/{cid}/students", json={"emails": emails}, headers=auth(T1)).json()
    assert len(result["added"]) == 25 and result["invalid"] == ["dana@"]
    assert client.get(f"/api/classes/{cid}", headers=auth(MGR)).json()["students"] == 25


def test_a_student_can_be_added_to_a_second_class(world):
    client, store = world
    a = make(client, name="A", teacher_email=T1).json()["id"]
    b = make(client, name="B", teacher_email=T2).json()["id"]
    client.post(f"/api/classes/{a}/students", json={"emails": "s@school.test"}, headers=auth(T1))
    again = client.post(f"/api/classes/{b}/students", json={"emails": "s@school.test"}, headers=auth(T2)).json()
    assert again["added"] == ["s@school.test"]
    assert [c["name"] for c in store.classes_of_student("s@school.test")] == ["A", "B"]
    twice = client.post(f"/api/classes/{a}/students", json={"emails": "s@school.test"}, headers=auth(T1)).json()
    assert twice["already_here"] == ["s@school.test"] and not twice["added"]


def test_a_teacher_cannot_add_themselves_as_a_student(world):
    client, _ = world
    cid = make(client, teacher_email=T1).json()["id"]
    result = client.post(f"/api/classes/{cid}/students", json={"emails": f"{T1} kid@school.test"}, headers=auth(T1)).json()
    assert result["teacher"] == [T1] and result["added"] == ["kid@school.test"]


def test_a_manager_can_use_any_roster_and_another_teacher_cannot(world):
    client, _ = world
    cid = make(client, teacher_email=T1).json()["id"]
    assert client.post(f"/api/classes/{cid}/students", json={"emails": "s@school.test"}, headers=auth(MGR)).status_code == 200
    assert client.post(f"/api/classes/{cid}/students", json={"emails": "s@school.test"}, headers=auth(T2)).status_code == 404
    assert client.delete(f"/api/classes/{cid}/students/s@school.test", headers=auth(T2)).status_code == 404
    assert client.post(f"/api/classes/{cid}/students", json={"emails": "s@school.test"}, headers=auth("kid@school.test")).status_code == 403


def test_the_teacher_removes_a_student_and_the_progress_stays(world):
    client, store = world
    cid = make(client, teacher_email=T1).json()["id"]
    client.post(f"/api/classes/{cid}/students", json={"emails": "s@school.test"}, headers=auth(T1))
    store.save_progress("u-s", "t_ext", started_at="then")
    assert client.delete(f"/api/classes/{cid}/students/S@school.test", headers=auth(T1)).status_code == 204
    assert client.delete(f"/api/classes/{cid}/students/s@school.test", headers=auth(T1)).status_code == 404
    assert store.get_progress("u-s", "t_ext")["started_at"] == "then"


def test_a_teacher_cannot_change_the_class_itself(world):
    client, _ = world
    cid = make(client, teacher_email=T1).json()["id"]
    assert client.put(f"/api/classes/{cid}", json=body("other"), headers=auth(T1)).status_code == 403
    assert client.delete(f"/api/classes/{cid}", headers=auth(T1)).status_code == 403
    assert client.get(f"/api/classes/{cid}", headers=auth(T1)).status_code == 403


def test_too_many_emails_in_one_go(world):
    client, _ = world
    cid = make(client, teacher_email=T1).json()["id"]
    emails = " ".join(f"s{i}@school.test" for i in range(201))
    assert client.post(f"/api/classes/{cid}/students", json={"emails": emails}, headers=auth(T1)).status_code == 422


# ---- the teacher's home and the manager's students (spec: Teacher home; Class and student lists)

def test_a_teacher_sees_only_the_classes_they_teach_with_their_students(world):
    client, _ = world
    make(client, name="A", teacher_email=T1, students="a@school.test")
    make(client, name="B", teacher_email=T1, students="b@school.test c@school.test")
    make(client, name="C", teacher_email=T2)
    mine = client.get("/api/teaching", headers=auth(T1)).json()
    assert [c["name"] for c in mine] == ["A", "B"] and [len(c["students"]) for c in mine] == [1, 2]
    assert mine[0]["students"][0] == {"email": "a@school.test", "signed_in": False}
    assert client.get("/api/teaching", headers=auth("kid@school.test")).status_code == 403
    assert client.get("/api/teaching", headers=auth(MGR)).status_code == 403          # a manager does not teach


def test_a_class_teacher_who_is_in_no_setting_still_gets_the_teacher_home(world):
    client, _ = world
    make(client, teacher_email="newcomer@school.test", students="a@school.test")
    assert [c["name"] for c in client.get("/api/teaching", headers=auth("newcomer@school.test")).json()] == ["ט'3"]
    assert client.get("/api/me", headers=auth("newcomer@school.test")).json()["teaching"][0]["name"] == "ט'3"


def test_a_developer_sees_every_class_as_a_teacher(world):
    client, _ = world
    make(client, name="A", teacher_email=T1)
    make(client, name="B", teacher_email=T2)
    assert [c["name"] for c in client.get("/api/teaching", headers=auth(DEV)).json()] == ["A", "B"]


def test_the_manager_sees_every_student_with_their_classes(world):
    client, _ = world
    make(client, name="A", students="x@school.test y@school.test")
    make(client, name="B", students="y@school.test")
    assert client.get("/api/students", headers=auth(MGR)).json() == [
        {"email": "x@school.test", "classes": ["A"]}, {"email": "y@school.test", "classes": ["A", "B"]}]
    assert client.get("/api/students", headers=auth(T1)).status_code == 403


def test_a_database_that_refuses_a_save_gives_a_clear_503_not_a_name_clash(world):
    from mathly2.store import StoreUnavailable
    client, store = world
    cid = make(client).json()["id"]
    def refuse(*args, **kwargs):
        raise StoreUnavailable("supabase refused (400): column lessons does not exist")
    store.update_class = refuse
    answer = client.put(f"/api/classes/{cid}", json=body("ט'3"), headers=auth(MGR))
    assert answer.status_code == 503 and "המיגרציות" in answer.json()["detail"] and "שם" not in answer.json()["detail"]
