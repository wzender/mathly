"""The permission matrix, checked against the real routes: every /api route says which permission it needs, and a caller whose
roles lack it is refused with 403, whatever the route does. Routes are read from the app itself, so a new route that is not
listed here fails the test and must be given a permission."""
import re

import pytest
from fastapi.testclient import TestClient

from mathly2.access import ROLES, allowed
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

PUBLIC = {("GET", "/api/health")}
ANY_SIGNED_IN = {("GET", "/api/me")}
NEEDS = {   # (method, path) -> permission
    ("GET", "/api/lessons"): "path.use",
    ("GET", "/api/dev/status"): "dev.status",
    ("GET", "/api/subjects"): "content.manage",
    ("POST", "/api/subjects"): "content.manage",
    ("PUT", "/api/subjects/{subject_id}"): "content.manage",
    ("DELETE", "/api/subjects/{subject_id}"): "content.manage",
    ("PUT", "/api/subjects/{subject_id}/order"): "content.manage",
    ("POST", "/api/subjects/{subject_id}/lessons"): "content.load",
    ("POST", "/api/worksheets"): "content.manage",
    ("GET", "/api/subjects/lessons/{lesson_id}"): "content.manage",
    ("PUT", "/api/subjects/lessons/{lesson_id}/draft"): "content.manage",
    ("POST", "/api/subjects/lessons/{lesson_id}/publish"): "content.manage",
    ("POST", "/api/subjects/lessons/{lesson_id}/unpublish"): "content.manage",
    ("POST", "/api/worksheets/{lesson_id}/files"): "content.manage",
    ("GET", "/api/worksheets/{lesson_id}"): "content.manage",
    ("GET", "/api/worksheets/{lesson_id}/pages/{index}"): "content.manage",
    ("GET", "/api/worksheets/{lesson_id}/text"): "content.manage",
    ("POST", "/api/worksheets/{lesson_id}/draft"): "content.manage",
    ("GET", "/api/dev/activity"): "dev.status",          # no role lists it: the developer's alone
    ("GET", "/api/path"): "path.use",
    ("GET", "/api/my-subjects"): "path.use",
    ("GET", "/api/collection"): "path.use",
    ("GET", "/api/teaching/tests"): "class.teach",
    ("POST", "/api/classes/{class_id}/tests"): "class.teach",
    ("PUT", "/api/tests/{test_id}"): "class.teach",
    ("DELETE", "/api/tests/{test_id}"): "class.teach",
    ("GET", "/api/home"): "path.use",
    ("POST", "/api/lessons/{lesson_id}/round/start"): "path.use",
    ("GET", "/api/rounds/{round_id}"): "path.use",
    ("POST", "/api/rounds/{round_id}/answer"): "path.use",
    ("POST", "/api/tests/{test_id}/exercise/{number}/start"): "path.use",
    ("POST", "/api/tests/{test_id}/simulation/start"): "path.use",
    ("GET", "/api/tests/{test_id}"): "path.use",
    ("GET", "/api/lessons/{lesson_id}/quiz"): "path.use",
    ("POST", "/api/lessons/{lesson_id}/quiz/start"): "path.use",
    ("GET", "/api/attempts/{attempt_id}"): "path.use",
    ("PUT", "/api/attempts/{attempt_id}/answers"): "path.use",
    ("POST", "/api/attempts/{attempt_id}/submit"): "path.use",
    ("GET", "/api/grades"): "path.use",
    ("DELETE", "/api/classes/{class_id}/pictures/{email}"): "class.roster",
    ("GET", "/api/teaching/counts"): "class.teach",
    ("GET", "/api/teaching/inbox"): "class.teach",
    ("GET", "/api/submissions/{submission_id}"): "class.teach",
    ("POST", "/api/submissions/{submission_id}/grade"): "class.teach",
    ("POST", "/api/submissions/{submission_id}/return"): "class.teach",
    ("GET", "/api/assignments"): "path.use",
    ("GET", "/api/assignments/{assignment_id}"): "path.use",
    ("POST", "/api/assignments/{assignment_id}/submission"): "path.use",
    ("POST", "/api/assignments/pages"): "class.teach",
    ("POST", "/api/classes/{class_id}/assignments"): "class.teach",
    ("GET", "/api/teaching/assignments"): "class.teach",
    ("DELETE", "/api/assignments/{assignment_id}"): "class.teach",
    ("GET", "/api/push/key"): "path.use",
    ("POST", "/api/push/subscribe"): "path.use",
    ("POST", "/api/push/unsubscribe"): "path.use",
    ("POST", "/api/photo-requests"): "path.use",
    ("GET", "/api/photo-requests/open"): "path.use",
    ("GET", "/api/photo-requests/{request_id}"): "path.use",
    ("POST", "/api/photo-requests/{request_id}/start"): "path.use",
    ("POST", "/api/photo-requests/{request_id}/picture"): "path.use",
    ("POST", "/api/pictures"): "path.use",
    ("GET", "/api/pictures/{picture_id}"): "path.use",
    ("GET", "/api/comets"): "path.use",
    ("POST", "/api/comets/catch"): "path.use",
    ("GET", "/api/skills/{skill_id}"): "path.use",
    ("POST", "/api/skills/{skill_id}/help"): "path.use",
    ("POST", "/api/skills/{skill_id}/answer"): "path.use",
    ("POST", "/api/skills/{skill_id}/round"): "path.use",
    ("GET", "/api/classes"): "classes.manage",
    ("POST", "/api/classes"): "classes.manage",
    ("GET", "/api/classes/{class_id}"): "classes.manage",
    ("PUT", "/api/classes/{class_id}"): "classes.manage",
    ("GET", "/api/classes/{class_id}/progress"): "class.teach",
    ("POST", "/api/ai/photo"): "path.use",
    ("POST", "/api/assignments/{assignment_id}/ai-check"): "path.use",
    ("POST", "/api/assignments/{assignment_id}/look-again"): "path.use",
    ("GET", "/api/ai/requests"): "path.use",
    ("GET", "/api/ai/status"): "path.use",
    ("GET", "/api/review"): "path.use",
    ("POST", "/api/review/answer"): "path.use",
    ("GET", "/api/ai/requests/{request_id}"): "path.use",
    ("POST", "/api/ai/requests/{request_id}/cancel"): "path.use",
    ("GET", "/api/ai/queue"): "class.teach",
    ("POST", "/api/ai/requests/{request_id}/send"): "class.teach",
    ("POST", "/api/ai/requests/{request_id}/decline"): "class.teach",
    ("POST", "/api/ai/batch"): "class.teach",
    ("POST", "/api/submissions/{submission_id}/ai-check"): "class.teach",
    ("GET", "/api/curriculum"): "classes.manage",
    ("PUT", "/api/curriculum"): "classes.manage",
    ("DELETE", "/api/classes/{class_id}"): "classes.manage",
    ("POST", "/api/classes/{class_id}/students"): "class.roster",
    ("DELETE", "/api/classes/{class_id}/students/{email}"): "class.roster",
    ("GET", "/api/teaching"): "class.teach",
    ("GET", "/api/students"): "students.list",
    ("GET", "/api/accounts"): "roles.manage",
    ("POST", "/api/accounts/{email}/roles/{role}"): "roles.manage",
    ("DELETE", "/api/accounts/{email}/roles/{role}"): "roles.manage",
}
WHO = {"student": "kid@school.test", "teacher": "t@school.test", "manager": "mgr@school.test",
       "admin": "adm@school.test", "developer": "dev@school.test"}


def api_routes(app):
    for path, methods in app.openapi()["paths"].items():
        if path.startswith("/api"):
            for method in sorted(methods):
                yield method.upper(), path


@pytest.fixture(scope="module")
def world():
    store = InMemoryStore()
    store.give_role(WHO["manager"], "manager", "setup")
    store.give_role(WHO["admin"], "admin", "setup")
    app = create_app(Settings(teachers=frozenset({WHO["teacher"]}), developers=frozenset({WHO["developer"]})), store=store)
    store.add_member(store.create_class("m@x.test", "A", lessons=["t"], teacher_email=WHO["teacher"])["id"], WHO["student"])
    return app, TestClient(app)


def call(client, method, path, email):
    url = path.format(skill_id="t_ext", lesson_id="t", attempt_id="x", round_id="x", test_id="1", number="1", picture_id="x", assignment_id="1", submission_id="1", request_id="x", class_id="1", subject_id="math", index="0", email="someone@school.test", role="teacher")
    sends = method in ("POST", "PUT", "PATCH")
    return client.request(method, url, headers={"Authorization": f"Bearer dev:{email}"}, json={} if sends else None)


def test_every_route_has_a_declared_permission(world):
    app, _ = world
    seen = set(api_routes(app))
    undeclared = seen - PUBLIC - ANY_SIGNED_IN - set(NEEDS)
    assert not undeclared, f"give these routes a permission in NEEDS: {sorted(undeclared)}"
    assert not (set(NEEDS) | ANY_SIGNED_IN | PUBLIC) - seen, "NEEDS lists a route that no longer exists"


@pytest.mark.parametrize("role", ROLES)
def test_a_role_is_refused_exactly_where_it_lacks_the_permission(world, role):
    _, client = world
    for (method, path), permission in sorted(NEEDS.items()):
        status = call(client, method, path, WHO[role]).status_code
        if allowed([role], permission):
            assert status != 403, f"{role} should reach {method} {path} but got 403"
        else:
            assert status == 403, f"{role} should be refused {method} {path} but got {status}"


@pytest.mark.parametrize("role", ROLES)
def test_every_role_can_read_its_own_access(world, role):
    _, client = world
    body = call(client, "GET", "/api/me", WHO[role]).json()
    assert body["email"] == WHO[role] and role in body["roles"]


def test_the_teachers_permission_does_not_reach_other_peoples_classes(world):
    _, client = world
    # the teacher has class.roster, but only for classes they teach: another class is not found
    other = client.post("/api/classes", json={"name": "B", "lessons": ["t"], "teacher_email": "else@school.test"},
                        headers={"Authorization": f"Bearer dev:{WHO['manager']}"}).json()["id"]
    refused = client.post(f"/api/classes/{other}/students", json={"emails": "x@school.test"},
                          headers={"Authorization": f"Bearer dev:{WHO['teacher']}"})
    assert refused.status_code == 404


def test_the_manager_and_admin_cannot_read_a_students_learning_data(world):
    _, client = world
    for role in ("manager", "admin"):
        for path in ("/api/path", "/api/collection", "/api/skills/t_ext", "/api/lessons"):
            assert call(client, "GET", path, WHO[role]).status_code == 403, (role, path)
