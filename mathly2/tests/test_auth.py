import io
import json
import urllib.error

import pytest
from fastapi.testclient import TestClient

from mathly2 import auth
from mathly2.auth import AuthUnavailable, DevAuthenticator, SupabaseAuthenticator
from mathly2.config import Settings
from mathly2.main import create_app

TEACHER = "teacher@school.test"


@pytest.fixture
def client():
    return TestClient(create_app(Settings(teachers=frozenset({TEACHER}))))


def sign(email):
    return {"Authorization": f"Bearer dev:{email}"}


def test_no_token_is_refused(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer dev:not-an-email"}).status_code == 401


def me(client, email):
    return client.get("/api/me", headers=sign(email)).json()


def test_a_listed_teacher_is_a_teacher(client):
    body = me(client, TEACHER)
    assert body["email"] == TEACHER and body["roles"] == ["teacher"] and body["classes"] == [] and body["teaching"] == []
    assert "class.teach" in body["permissions"] and "classes.manage" not in body["permissions"]
    assert me(client, "Teacher@School.test")["roles"] == ["teacher"]            # case does not matter


def test_everyone_else_is_a_student(client):
    body = me(client, "kid@school.test")
    assert body["roles"] == ["student"] and body["permissions"] == ["path.use"] and body["classes"] == []


def test_developers_and_first_admins_come_from_the_settings():
    app = create_app(Settings(developers=frozenset({"dev@school.test"}), admins=frozenset({"head@school.test"})))
    client = TestClient(app)
    assert me(client, "dev@school.test")["roles"] == ["developer"] and me(client, "dev@school.test")["permissions"] == ["*"]
    assert me(client, "head@school.test")["roles"] == ["admin"] and me(client, "head@school.test")["permissions"] == ["roles.manage"]


def test_page_carries_only_public_settings():
    page = TestClient(create_app(Settings())).get("/").text
    assert '"devSignIn": true' in page and "__CONFIG__" not in page
    page = TestClient(create_app(Settings(supabase_url="https://p.test", supabase_key="pub", supabase_secret="SECRET-VALUE"))).get("/").text
    assert '"supabaseKey": "pub"' in page and '"devSignIn": false' in page and "SECRET-VALUE" not in page


def test_half_configured_supabase_does_not_fall_back_to_dev_sign_in():
    with pytest.raises(ValueError, match="all of SUPABASE_URL"):
        create_app(Settings(supabase_url="https://p.test"))


def test_dev_sign_in_is_off_when_supabase_is_on():
    app = create_app(Settings(supabase_url="https://p.test", supabase_key="pub", supabase_secret="sec"))
    assert isinstance(app.state.authenticator, SupabaseAuthenticator)
    assert TestClient(app).get("/api/me", headers=sign("kid@school.test")).status_code in (401, 503)


def supabase_returns(monkeypatch, payload=None, error=None):
    """Stand in for the HTTP call to Supabase's /auth/v1/user: the calls made are returned as (url, headers)."""
    calls = []

    def fake(method, url, headers=None, body=None, timeout=0):
        calls.append((url, headers or {}))
        if error:
            raise error
        return 200, json.dumps(payload).encode()
    monkeypatch.setattr(auth.pooled, "request", fake)
    return calls


def test_supabase_user_is_checked_with_the_token_and_cached(monkeypatch):
    calls = supabase_returns(monkeypatch, {"id": "u1", "email": "Kid@School.test", "email_confirmed_at": "2026-01-01"})
    a = SupabaseAuthenticator("https://p.test", "pub")
    assert a.user("tok") == {"id": "u1", "email": "kid@school.test"}
    assert a.user("tok")["id"] == "u1"
    assert len(calls) == 1 and calls[0][1]["Authorization"] == "Bearer tok" and calls[0][0].endswith("/auth/v1/user")


def test_an_unconfirmed_email_is_not_trusted(monkeypatch):
    supabase_returns(monkeypatch, {"id": "u1", "email": TEACHER})
    assert SupabaseAuthenticator("https://p.test", "pub").user("tok") is None


def test_rejected_token_and_outage(monkeypatch):
    supabase_returns(monkeypatch, error=urllib.error.HTTPError("u", 401, "no", {}, None))
    assert SupabaseAuthenticator("https://p.test", "pub").user("bad") is None
    supabase_returns(monkeypatch, error=urllib.error.URLError("down"))
    with pytest.raises(AuthUnavailable):
        SupabaseAuthenticator("https://p.test", "pub").user("tok")


def test_outage_gives_503(monkeypatch):
    class Down:
        def user(self, token): raise AuthUnavailable("down")
    app = create_app(Settings(), authenticator=Down())
    assert TestClient(app).get("/api/me", headers={"Authorization": "Bearer x"}).status_code == 503
