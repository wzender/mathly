"""Apply the migrations to a real local PostgreSQL and check the browser roles cannot touch the tables."""
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
pgserver = pytest.importorskip("pgserver")

MIGRATIONS = sorted((Path(__file__).parent.parent / "supabase" / "migrations").glob("*.sql"))


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp("postgres") / "data", cleanup_mode="delete")
    with psycopg.connect(server.get_uri(), autocommit=True) as c:
        c.execute("create role anon; create role authenticated; create role service_role bypassrls;")
        c.execute("grant usage on schema public to anon, authenticated, service_role;")
        for path in MIGRATIONS:
            c.execute(path.read_text(encoding="utf-8"))
    yield server.get_uri()
    server.cleanup()


def as_role(uri, role, sql, *params):
    with psycopg.connect(uri, autocommit=True) as c:
        c.execute(f"set role {role}")
        return c.execute(sql, params).fetchall() if sql.lstrip().lower().startswith("select") else c.execute(sql, params)


def test_server_role_can_use_the_tables(db):
    as_role(db, "service_role", "insert into public.m2_classes(name, teacher_email) values ('ט''3', 't@school.test')")
    rows = as_role(db, "service_role", "select name from public.m2_classes")
    assert rows == [("ט'3",)]


@pytest.mark.parametrize("role", ["authenticated", "anon"])
def test_browser_roles_are_refused(db, role):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "insert into public.m2_classes(name, teacher_email) values ('x', 'a@b.test')")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "select * from public.m2_class_members")


def test_row_level_security_is_on_and_has_no_policies(db):
    with psycopg.connect(db, autocommit=True) as c:
        on = dict(c.execute("select relname, relrowsecurity from pg_class where relname in ('m2_classes','m2_class_members')").fetchall())
        policies = c.execute("select count(*) from pg_policies where tablename like 'm2_%'").fetchone()[0]
    assert on == {"m2_classes": True, "m2_class_members": True}
    assert policies == 0


def test_a_student_email_can_belong_to_only_one_class(db):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("insert into public.m2_classes(name, teacher_email) values ('ח''1', 't@school.test')")
        ids = [r[0] for r in c.execute("select id from public.m2_classes order by id").fetchall()]
        c.execute("insert into public.m2_class_members(class_id, email) values (%s, 's@school.test')", (ids[0],))
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("insert into public.m2_class_members(class_id, email) values (%s, 's@school.test')", (ids[1],))
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'UPPER@school.test')", (ids[0],))
