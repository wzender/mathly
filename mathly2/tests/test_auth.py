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


def test_a_listed_teacher_is_a_teacher(client):
    assert client.get("/api/me", headers=sign(TEACHER)).json() == {"email": TEACHER, "role": "teacher", "class": None}
    assert client.get("/api/me", headers=sign("Teacher@School.test")).json()["role"] == "teacher"   # case does not matter


def test_everyone_else_is_a_student(client):
    assert client.get("/api/me", headers=sign("kid@school.test")).json() == {"email": "kid@school.test", "role": "student", "class": None}


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


class Reply(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def supabase_returns(monkeypatch, payload=None, error=None):
    calls = []

    def fake(request, timeout=0):
        calls.append(request)
        if error:
            raise error
        return Reply(json.dumps(payload).encode())
    monkeypatch.setattr(auth.urllib.request, "urlopen", fake)
    return calls


def test_supabase_user_is_checked_with_the_token_and_cached(monkeypatch):
    calls = supabase_returns(monkeypatch, {"id": "u1", "email": "Kid@School.test", "email_confirmed_at": "2026-01-01"})
    a = SupabaseAuthenticator("https://p.test", "pub")
    assert a.user("tok") == {"id": "u1", "email": "kid@school.test"}
    assert a.user("tok")["id"] == "u1"
    assert len(calls) == 1 and calls[0].headers["Authorization"] == "Bearer tok"


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
