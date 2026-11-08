import pytest
from fastapi.testclient import TestClient

from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

ADMIN, OTHER_ADMIN, HEAD = "admin@school.test", "admin2@school.test", "head@school.test"


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def build(admins=frozenset()):
    store = InMemoryStore()
    store.give_role(ADMIN, "admin", "setup")
    return TestClient(create_app(Settings(admins=admins, developers=frozenset({"dev@school.test"}), teachers=frozenset({"t@school.test"})), store=store)), store


@pytest.fixture
def client():
    return build()[0]


def test_only_an_admin_or_a_developer_reaches_the_accounts(client):
    assert client.get("/api/accounts").status_code == 401
    for who in ("kid@school.test", "t@school.test"):
        assert client.get("/api/accounts", headers=auth(who)).status_code == 403
        assert client.post("/api/accounts/x@school.test/roles/manager", headers=auth(who)).status_code == 403
    assert client.get("/api/accounts", headers=auth(ADMIN)).status_code == 200
    assert client.get("/api/accounts", headers=auth("dev@school.test")).status_code == 200


def test_a_role_given_before_the_first_sign_in_applies_at_it(client):
    assert client.post("/api/accounts/Rina@School.test/roles/manager", headers=auth(ADMIN)).status_code == 204
    assert client.get("/api/me", headers=auth("rina@school.test")).json()["roles"] == ["manager"]
    assert client.post("/api/classes", json={"name": "ט'3", "lessons": ["t"]}, headers=auth("rina@school.test")).status_code == 201


def test_the_accounts_list_shows_given_roles_and_roles_from_the_settings():
    client, store = build(admins=frozenset({HEAD}))
    client.post("/api/accounts/new@school.test/roles/teacher", headers=auth(HEAD))
    listed = {a["email"]: a for a in client.get("/api/accounts", headers=auth(HEAD)).json()}
    assert listed["new@school.test"]["roles"] == ["teacher"] and listed["new@school.test"]["from_settings"] == []
    assert listed[HEAD]["from_settings"] == ["admin"] and listed["dev@school.test"]["from_settings"] == ["developer"]
    assert listed["t@school.test"]["from_settings"] == ["teacher"] and listed[ADMIN]["roles"] == ["admin"]


def test_an_admin_takes_a_role_away_and_it_stops_applying(client):
    client.post("/api/accounts/rina@school.test/roles/manager", headers=auth(ADMIN))
    assert client.get("/api/me", headers=auth("rina@school.test")).json()["roles"] == ["manager"]
    assert client.delete("/api/accounts/rina@school.test/roles/manager", headers=auth(ADMIN)).status_code == 204
    assert client.get("/api/me", headers=auth("rina@school.test")).json()["roles"] == ["student"]
    assert client.delete("/api/accounts/rina@school.test/roles/manager", headers=auth(ADMIN)).status_code == 404


def test_the_developer_role_cannot_be_given_and_bad_input_is_refused(client):
    assert client.post("/api/accounts/x@school.test/roles/developer", headers=auth(ADMIN)).status_code == 422
    assert client.post("/api/accounts/x@school.test/roles/boss", headers=auth(ADMIN)).status_code == 422
    assert client.post("/api/accounts/not-an-email/roles/manager", headers=auth(ADMIN)).status_code == 422
    assert client.delete("/api/accounts/x@school.test/roles/developer", headers=auth(ADMIN)).status_code == 422


def test_the_last_admin_cannot_remove_their_own_admin_role(client):
    refused = client.delete(f"/api/accounts/{ADMIN}/roles/admin", headers=auth(ADMIN))
    assert refused.status_code == 409 and "האחרון" in refused.json()["detail"]
    assert client.get("/api/me", headers=auth(ADMIN)).json()["roles"] == ["admin"]


def test_one_of_two_admins_can_step_down(client):
    client.post(f"/api/accounts/{OTHER_ADMIN}/roles/admin", headers=auth(ADMIN))
    assert client.delete(f"/api/accounts/{ADMIN}/roles/admin", headers=auth(ADMIN)).status_code == 204
    assert client.get("/api/me", headers=auth(ADMIN)).json()["roles"] == ["student"]
    assert client.delete(f"/api/accounts/{OTHER_ADMIN}/roles/admin", headers=auth(OTHER_ADMIN)).status_code == 409


def test_an_admin_from_the_settings_lets_the_table_admin_step_down():
    client, _ = build(admins=frozenset({HEAD}))
    assert client.delete(f"/api/accounts/{ADMIN}/roles/admin", headers=auth(HEAD)).status_code == 204
    assert client.get("/api/me", headers=auth(HEAD)).json()["roles"] == ["admin"]
