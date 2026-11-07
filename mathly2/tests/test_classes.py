import pytest
from fastapi.testclient import TestClient

from mathly2.classes import parse_emails
from mathly2.config import Settings
from mathly2.main import create_app

T1, T2 = "t1@school.test", "t2@school.test"


@pytest.fixture
def client():
    return TestClient(create_app(Settings(teachers=frozenset({T1, T2}))))


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def make_class(client, teacher=T1, name="ט'3"):
    return client.post("/api/classes", json={"name": name}, headers=auth(teacher))


def test_parse_emails_handles_pasted_lists():
    valid, invalid = parse_emails(" A@x.test, b@x.test;\nc@x.test  a@x.test not-an-email ")
    assert valid == ["a@x.test", "b@x.test", "c@x.test"] and invalid == ["not-an-email"]


def test_teacher_creates_and_lists_classes(client):
    created = make_class(client)
    assert created.status_code == 201 and created.json()["name"] == "ט'3"
    assert client.get("/api/classes", headers=auth(T1)).json() == [{"id": created.json()["id"], "name": "ט'3", "students": 0}]
    assert client.get("/api/classes", headers=auth(T2)).json() == []


def test_class_name_is_trimmed_checked_and_unique(client):
    assert make_class(client, name="  ח'  1 ").json()["name"] == "ח' 1"
    assert make_class(client, name="ח' 1").status_code == 409
    assert make_class(client, name="   ").status_code == 422
    assert make_class(client, name="x" * 61).status_code == 422


def test_students_cannot_use_class_endpoints(client):
    kid = auth("kid@school.test")
    assert client.get("/api/classes", headers=kid).status_code == 403
    assert client.post("/api/classes", json={"name": "A"}, headers=kid).status_code == 403
    assert client.get("/api/classes").status_code == 401


def test_add_a_list_of_students(client):
    cid = make_class(client).json()["id"]
    emails = "\n".join(f"s{i}@school.test" for i in range(25))
    result = client.post(f"/api/classes/{cid}/students", json={"emails": emails}, headers=auth(T1)).json()
    assert len(result["added"]) == 25 and not result["elsewhere"] and not result["invalid"]
    shown = client.get(f"/api/classes/{cid}", headers=auth(T1)).json()
    assert len(shown["students"]) == 25 and shown["students"][0] == {"email": "s0@school.test", "signed_in": False}
    assert client.get("/api/classes", headers=auth(T1)).json()[0]["students"] == 25


def test_student_in_another_class_is_reported_not_added_twice(client):
    a = make_class(client, name="A").json()["id"]
    b = make_class(client, T2, "B").json()["id"]
    client.post(f"/api/classes/{a}/students", json={"emails": "s@school.test"}, headers=auth(T1))
    result = client.post(f"/api/classes/{b}/students", json={"emails": "s@school.test new@school.test"}, headers=auth(T2)).json()
    assert result["elsewhere"] == [{"email": "s@school.test", "class_name": "A"}] and result["added"] == ["new@school.test"]
    again = client.post(f"/api/classes/{a}/students", json={"emails": "s@school.test"}, headers=auth(T1)).json()
    assert again["already_here"] == ["s@school.test"] and not again["added"]


def test_a_teacher_cannot_touch_another_teachers_class(client):
    cid = make_class(client).json()["id"]
    assert client.get(f"/api/classes/{cid}", headers=auth(T2)).status_code == 404
    assert client.post(f"/api/classes/{cid}/students", json={"emails": "s@school.test"}, headers=auth(T2)).status_code == 404
    assert client.delete(f"/api/classes/{cid}/students/s@school.test", headers=auth(T2)).status_code == 404


def test_remove_a_student(client):
    cid = make_class(client).json()["id"]
    client.post(f"/api/classes/{cid}/students", json={"emails": "s@school.test"}, headers=auth(T1))
    assert client.delete(f"/api/classes/{cid}/students/S@school.test", headers=auth(T1)).status_code == 204
    assert client.delete(f"/api/classes/{cid}/students/s@school.test", headers=auth(T1)).status_code == 404
    assert client.get(f"/api/classes/{cid}", headers=auth(T1)).json()["students"] == []


def test_too_many_emails_in_one_go(client):
    cid = make_class(client).json()["id"]
    emails = " ".join(f"s{i}@school.test" for i in range(201))
    assert client.post(f"/api/classes/{cid}/students", json={"emails": emails}, headers=auth(T1)).status_code == 422
