import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mathly2.access import GRANTABLE, PERMISSIONS, ROLES, allowed, need, permissions_of

KNOWN = set().union(*PERMISSIONS.values()) - {"*"}


def test_there_are_five_roles_and_developer_is_never_grantable():
    assert ROLES == ("student", "teacher", "manager", "admin", "developer")
    assert "developer" not in GRANTABLE and set(GRANTABLE) < set(ROLES)


@pytest.mark.parametrize("role,yes,no", [
    ("student", {"path.use"}, {"class.teach", "class.roster", "classes.manage", "students.list", "roles.manage", "content.manage"}),
    ("teacher", {"path.use", "class.teach", "class.roster"}, {"classes.manage", "students.list", "roles.manage", "content.manage"}),
    ("manager", {"classes.manage", "class.roster", "students.list", "content.manage"}, {"path.use", "class.teach", "roles.manage"}),
    ("admin", {"roles.manage"}, {"path.use", "class.teach", "class.roster", "classes.manage", "students.list", "content.manage"}),
])
def test_each_role_has_only_its_permissions(role, yes, no):
    for permission in yes:
        assert allowed([role], permission), (role, permission)
    for permission in no:
        assert not allowed([role], permission), (role, permission)


def test_developer_has_every_permission_even_ones_not_invented_yet():
    assert all(allowed(["developer"], p) for p in KNOWN | {"something.new"})


def test_several_roles_add_up():
    assert permissions_of(["manager", "teacher"]) >= {"classes.manage", "class.teach", "path.use"}
    assert not allowed([], "path.use") and permissions_of(["nonsense"]) == frozenset()


def test_manager_and_admin_see_no_learning_data():
    # learning data is the student's path and a teacher's view of their own classes: neither role has them
    for role in ("manager", "admin"):
        assert not allowed([role], "path.use") and not allowed([role], "class.teach")


def test_need_refuses_a_missing_permission_with_403_and_a_missing_sign_in_with_401():
    from mathly2.auth import DevAuthenticator
    app = FastAPI()
    app.state.authenticator = DevAuthenticator()

    class Roles:
        def resolve(self, email, source=None):
            return {"boss@x.test": frozenset({"manager"})}.get(email, frozenset({"student"}))
    app.state.roles = Roles()

    @app.get("/manage")
    def manage(user: dict = Depends(need("classes.manage"))):
        return {"ok": user["email"]}

    client = TestClient(app)
    assert client.get("/manage").status_code == 401
    assert client.get("/manage", headers={"Authorization": "Bearer dev:kid@x.test"}).status_code == 403
    assert client.get("/manage", headers={"Authorization": "Bearer dev:boss@x.test"}).json() == {"ok": "boss@x.test"}
