"""Every /api route except health refuses a caller without a valid token. The routes are read from the app itself,
so an endpoint added later is covered without touching this test."""
import re

import pytest
from fastapi.testclient import TestClient

from mathly2.config import Settings
from mathly2.main import create_app

PUBLIC = {"/api/health"}


def api_routes(app):
    # Read from the OpenAPI schema: app.routes does not list routes added with include_router.
    for path, methods in app.openapi()["paths"].items():
        if path.startswith("/api"):
            for method in sorted(methods):
                yield method.upper(), path


@pytest.fixture(scope="module")
def app():
    return create_app(Settings(teachers=frozenset({"t@school.test"})))


def test_there_are_routes_to_check(app):
    assert len(list(api_routes(app))) >= 8
    assert ('DELETE', '/api/classes/{class_id}/students/{email}') in set(api_routes(app))


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer "}, {"Authorization": "Bearer dev:nobody"}, {"Authorization": "Basic abc"}])
def test_every_api_route_refuses_a_caller_without_a_valid_token(app, headers):
    client = TestClient(app)
    for method, path in api_routes(app):
        if path in PUBLIC:
            continue
        url = re.sub(r"\{[^}]*\}", "1", path)
        response = client.request(method, url, headers=headers, json={} if method in ("POST", "PUT", "PATCH") else None)
        assert response.status_code == 401, f"{method} {path} answered {response.status_code} without a token"


def test_health_stays_public(app):
    assert TestClient(app).get("/api/health").status_code == 200


def test_no_secret_in_the_page():
    page = TestClient(create_app(Settings(supabase_url="https://p.test", supabase_key="pub", supabase_secret="SECRET-VALUE"))).get("/")
    assert "SECRET-VALUE" not in page.text
