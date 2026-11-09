import pytest
from fastapi.testclient import TestClient

from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

MGR, TEACHER, KID = "mgr@school.test", "t@school.test", "kid@school.test"


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


@pytest.fixture
def setup():
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    client = TestClient(create_app(Settings(teachers=frozenset({TEACHER})), store=store))
    return client, store


def make(client, name="ט'3", lessons=("t",), students=""):
    return client.post("/api/classes", json={"name": name, "lessons": list(lessons), "teacher_email": TEACHER, "students": students},
                       headers=auth(MGR)).json()["id"]


def test_a_student_in_no_class_gets_no_class_and_no_lessons(setup):
    client, _ = setup
    me = client.get("/api/me", headers=auth(KID)).json()
    assert me["roles"] == ["student"] and me["classes"] == [] and me["teaching"] == []
    assert client.get("/api/lessons", headers=auth(KID)).status_code == 403


def test_first_sign_in_links_the_account_to_the_class_entry(setup):
    client, store = setup
    cid = make(client, students=KID)
    assert store.members(cid)[0]["user_id"] is None
    me = client.get("/api/me", headers=auth(KID)).json()
    assert me["classes"] == [{"id": cid, "name": "ט'3"}]
    assert store.members(cid)[0]["user_id"]
    assert [lesson["id"] for lesson in client.get("/api/lessons", headers=auth(KID)).json()] == [l["id"] for l in load_bank().lessons_with_skills()]


def test_a_student_of_two_classes_has_the_lessons_of_both(setup):
    client, _ = setup
    make(client, "A", ("t", "t2"), KID)
    make(client, "B", ("t2", "k"), KID)
    assert len(client.get("/api/lessons", headers=auth(KID)).json()) == len(load_bank().lessons_with_skills())
    assert [c["name"] for c in client.get("/api/me", headers=auth(KID)).json()["classes"]] == ["A", "B"]


def test_a_removed_student_loses_the_lessons(setup):
    client, _ = setup
    cid = make(client, students=KID)
    assert client.get("/api/lessons", headers=auth(KID)).status_code == 200
    client.delete(f"/api/classes/{cid}/students/{KID}", headers=auth(TEACHER))
    assert client.get("/api/lessons", headers=auth(KID)).status_code == 403


def test_a_deleted_class_takes_its_lessons_away(setup):
    client, _ = setup
    cid = make(client, students=KID)
    client.delete(f"/api/classes/{cid}", headers=auth(MGR))
    assert client.get("/api/lessons", headers=auth(KID)).status_code == 403


def test_a_teacher_sees_every_lesson_and_a_manager_no_learning_data(setup):
    client, _ = setup
    assert len(client.get("/api/lessons", headers=auth(TEACHER)).json()) == 24
    assert client.get("/api/lessons", headers=auth(MGR)).status_code == 403
    assert client.get("/api/path", headers=auth(MGR)).status_code == 403
