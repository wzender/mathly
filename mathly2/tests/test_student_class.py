import pytest
from fastapi.testclient import TestClient

from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

TEACHER, KID = "t@school.test", "kid@school.test"


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


@pytest.fixture
def setup():
    store = InMemoryStore()
    client = TestClient(create_app(Settings(teachers=frozenset({TEACHER})), store=store))
    return client, store


def test_student_in_no_class_gets_no_class_and_no_lessons(setup):
    client, _ = setup
    me = client.get("/api/me", headers=auth(KID)).json()
    assert me == {"email": KID, "role": "student", "class": None}
    assert client.get("/api/lessons", headers=auth(KID)).status_code == 403


def test_first_sign_in_links_the_account_to_the_class_entry(setup):
    client, store = setup
    cid = client.post("/api/classes", json={"name": "ט'3"}, headers=auth(TEACHER)).json()["id"]
    client.post(f"/api/classes/{cid}/students", json={"emails": KID}, headers=auth(TEACHER))
    assert client.get(f"/api/classes/{cid}", headers=auth(TEACHER)).json()["students"][0]["signed_in"] is False
    me = client.get("/api/me", headers=auth(KID)).json()
    assert me["class"] == {"id": cid, "name": "ט'3"}
    assert store.membership(KID)["user_id"]
    assert client.get(f"/api/classes/{cid}", headers=auth(TEACHER)).json()["students"][0]["signed_in"] is True
    assert len(client.get("/api/lessons", headers=auth(KID)).json()) == 24


def test_a_removed_student_loses_the_lessons(setup):
    client, _ = setup
    cid = client.post("/api/classes", json={"name": "A"}, headers=auth(TEACHER)).json()["id"]
    client.post(f"/api/classes/{cid}/students", json={"emails": KID}, headers=auth(TEACHER))
    assert client.get("/api/lessons", headers=auth(KID)).status_code == 200
    client.delete(f"/api/classes/{cid}/students/{KID}", headers=auth(TEACHER))
    assert client.get("/api/lessons", headers=auth(KID)).status_code == 403


def test_teacher_has_no_class_and_still_sees_lessons(setup):
    client, _ = setup
    assert client.get("/api/me", headers=auth(TEACHER)).json()["class"] is None
    assert client.get("/api/lessons", headers=auth(TEACHER)).status_code == 200
