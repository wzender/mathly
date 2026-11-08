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


def _class(c, name, teacher=None, lessons="{t}"):
    return c.execute("insert into public.m2_classes(name, teacher_email, created_by, lessons) values (%s, %s, 'mgr@school.test', %s) returning id",
                     (name, teacher, lessons)).fetchone()[0]


def test_a_student_can_be_in_several_classes_but_only_once_in_each(db):
    with psycopg.connect(db, autocommit=True) as c:
        a, b = _class(c, "ו'1"), _class(c, "ו'2")
        c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'multi@school.test')", (a,))
        c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'multi@school.test')", (b,))
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'multi@school.test')", (a,))
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'UPPER@school.test')", (a,))


def test_class_names_are_unique_ignoring_case_across_creators(db):
    with psycopg.connect(db, autocommit=True) as c:
        _class(c, "Dalet")
        with pytest.raises(psycopg.errors.UniqueViolation):
            _class(c, "dALET", teacher="someone@school.test")


def test_a_class_can_have_no_teacher_and_has_the_ai_off_with_150_checks(db):
    with psycopg.connect(db, autocommit=True) as c:
        cid = _class(c, "ז'1")
        assert c.execute("select teacher_email, ai_enabled, ai_daily_checks, lessons from public.m2_classes where id = %s", (cid,)).fetchone() == (None, False, 150, ["t"])
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("update public.m2_classes set ai_daily_checks = -1 where id = %s", (cid,))


def test_a_teacher_cannot_also_be_a_student_of_the_same_class(db):
    with psycopg.connect(db, autocommit=True) as c:
        cid = _class(c, "ח'7", teacher="teach@school.test")
        with pytest.raises(psycopg.errors.CheckViolation, match="teacher_is_student"):
            c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'teach@school.test')", (cid,))
        c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'kid7@school.test')", (cid,))
        with pytest.raises(psycopg.errors.CheckViolation, match="teacher_is_student"):
            c.execute("update public.m2_classes set teacher_email = 'kid7@school.test' where id = %s", (cid,))
        other = _class(c, "ח'8")
        c.execute("insert into public.m2_class_members(class_id, email) values (%s, 'teach@school.test')", (other,))   # a student elsewhere is fine


def test_roles_accept_only_the_four_grantable_ones_in_lower_case(db):
    with psycopg.connect(db, autocommit=True) as c:
        for role in ("student", "teacher", "manager", "admin"):
            c.execute("insert into public.m2_roles(email, role, granted_by) values ('grant@school.test', %s, 'a@school.test')", (role,))
        for bad in (("grant@school.test", "developer"), ("grant@school.test", "boss"), ("Grant@school.test", "admin")):
            with pytest.raises(psycopg.errors.CheckViolation):
                c.execute("insert into public.m2_roles(email, role) values (%s, %s)", bad)
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("insert into public.m2_roles(email, role) values ('grant@school.test', 'admin')")


def test_take_role_in_one_step_keeps_the_last_admin(db):
    take = lambda email, role, settings=0: as_role(db, "service_role", "select public.m2_take_role(%s, %s, %s)", email, role, settings)[0][0]
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("delete from public.m2_roles where role = 'admin'")
        c.execute("insert into public.m2_roles(email, role) values ('adm1@school.test', 'admin'), ('adm2@school.test', 'admin'), ('mgr@school.test', 'manager')")
    assert take("nobody@school.test", "admin") == "absent"
    assert take("mgr@school.test", "manager") == "removed"
    assert take("adm1@school.test", "admin") == "removed"
    assert take("adm2@school.test", "admin") == "last_admin"          # the only one left stays
    assert take("adm2@school.test", "admin", 1) == "removed"          # unless the settings name another admin
    with psycopg.connect(db, autocommit=True) as c:
        assert c.execute("select count(*) from public.m2_roles where role = 'admin'").fetchone()[0] == 0


@pytest.mark.parametrize("role", ["authenticated", "anon"])
def test_browser_roles_cannot_read_roles_or_take_one_away(db, role):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "select * from public.m2_roles")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "select public.m2_take_role('a@school.test', 'admin', 0)")


def test_row_level_security_is_on_for_roles(db):
    with psycopg.connect(db, autocommit=True) as c:
        assert c.execute("select relrowsecurity from pg_class where relname = 'm2_roles'").fetchone()[0] is True
        assert c.execute("select count(*) from pg_policies where tablename like 'm2_%'").fetchone()[0] == 0


# --- skill learning (task 2.1) ---

USER = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"


def test_daily_correct_counts_only_correct_answers_per_student_and_day(db):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("delete from public.m2_answers")
        rows = [(USER, "s", "q1", True, True, "2026-11-02"), (USER, "s", "q2", True, False, "2026-11-02"),
                (USER, "s", "q3", False, True, "2026-11-02"), (USER, "s", "q4", True, True, "2026-11-03"),
                (OTHER, "s", "q1", True, True, "2026-11-02")]
        for user, skill, key, correct, counted, day in rows:
            c.execute("insert into public.m2_answers(user_id, skill_id, question_key, correct, counted, day) "
                      "values (%s, %s, %s, %s, %s, %s)", (user, skill, key, correct, counted, day))
    got = as_role(db, "service_role", "select to_char(day, 'YYYY-MM-DD'), correct from public.m2_daily_correct "
                  "where user_id = %s order by day", USER)
    assert got == [("2026-11-02", 2), ("2026-11-03", 1)]    # the helped answer counts; the wrong one does not


def test_progress_row_is_unique_per_student_and_skill_with_defaults(db):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("insert into public.m2_skill_progress(user_id, skill_id) values (%s, 'a')", (USER,))
        row = c.execute("select current_key, current_helped, started_at, mastered_at from public.m2_skill_progress "
                        "where user_id = %s and skill_id = 'a'", (USER,)).fetchone()
        assert row == (None, False, None, None)
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("insert into public.m2_skill_progress(user_id, skill_id) values (%s, 'a')", (USER,))


def test_progress_no_longer_has_the_stage_columns_and_keeps_the_rest(db):
    with psycopg.connect(db, autocommit=True) as c:
        columns = {r[0] for r in c.execute("select column_name from information_schema.columns "
                                           "where table_schema = 'public' and table_name = 'm2_skill_progress'").fetchall()}
    assert columns == {"user_id", "skill_id", "current_key", "current_helped", "started_at", "mastered_at", "round_start"}


def test_round_start_is_empty_for_old_rows_and_cannot_be_negative(db):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("insert into public.m2_skill_progress(user_id, skill_id) values ('33333333-3333-3333-3333-333333333333', 'r')")
        assert c.execute("select round_start from public.m2_skill_progress where skill_id = 'r'").fetchone() == (None,)
        c.execute("update public.m2_skill_progress set round_start = 10 where skill_id = 'r'")
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("update public.m2_skill_progress set round_start = -1 where skill_id = 'r'")


@pytest.mark.parametrize("role", ["authenticated", "anon"])
@pytest.mark.parametrize("table", ["m2_answers", "m2_skill_progress", "m2_daily_correct"])
def test_browser_roles_cannot_read_skill_learning_objects(db, role, table):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, f"select * from public.{table}")


@pytest.mark.parametrize("role", ["authenticated", "anon"])
def test_browser_roles_cannot_write_answers(db, role):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "insert into public.m2_answers(user_id, skill_id, question_key, correct, day) "
                          "values (%s, 's', 'q', true, '2026-11-02')", USER)


def test_row_level_security_is_on_for_the_new_tables(db):
    with psycopg.connect(db, autocommit=True) as c:
        on = dict(c.execute("select relname, relrowsecurity from pg_class "
                            "where relname in ('m2_answers','m2_skill_progress')").fetchall())
        policies = c.execute("select count(*) from pg_policies where tablename like 'm2_%'").fetchone()[0]
    assert on == {"m2_answers": True, "m2_skill_progress": True}
    assert policies == 0


def test_server_role_can_insert_answers_and_progress(db):
    as_role(db, "service_role", "insert into public.m2_answers(user_id, skill_id, question_key, correct, day) "
                                "values (%s, 'svc', 'q', true, '2026-11-04')", USER)
    as_role(db, "service_role", "insert into public.m2_skill_progress(user_id, skill_id) values (%s, 'svc')", USER)


def test_last_answered_gives_the_newest_day_per_student_and_skill(db):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("delete from public.m2_answers")
        for user, skill, key, day in ((USER, "s", "q1", "2026-11-02"), (USER, "s", "q2", "2026-11-09"), (USER, "t", "q1", "2026-11-03"),
                                      (OTHER, "s", "q1", "2026-11-20")):
            c.execute("insert into public.m2_answers(user_id, skill_id, question_key, correct, counted, day) values (%s, %s, %s, false, false, %s)",
                      (user, skill, key, day))
    got = as_role(db, "service_role", "select skill_id, to_char(day, 'YYYY-MM-DD') from public.m2_last_answered where user_id = %s order by skill_id", USER)
    assert got == [("s", "2026-11-09"), ("t", "2026-11-03")]


@pytest.mark.parametrize("role", ["authenticated", "anon"])
def test_browser_roles_cannot_read_the_reward_tables(db, role):
    for table in ("m2_comets", "m2_reward_state", "m2_last_answered"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_role(db, role, f"select * from public.{table}")


def test_a_student_catches_each_comet_once_and_has_one_state_row(db):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("insert into public.m2_comets(user_id, comet_id) values (%s, 'pi')", (USER,))
        c.execute("insert into public.m2_comets(user_id, comet_id) values (%s, 'pi')", (OTHER,))        # another student may have it too
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("insert into public.m2_comets(user_id, comet_id) values (%s, 'pi')", (USER,))
        c.execute("insert into public.m2_reward_state(user_id) values (%s)", (USER,))
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("insert into public.m2_reward_state(user_id) values (%s)", (USER,))
        assert c.execute("select last_comet_day, last_catch_day from public.m2_reward_state where user_id = %s", (USER,)).fetchone() == (None, None)


def test_attempts_have_defaults_and_refuse_bad_values(db):
    with psycopg.connect(db, autocommit=True) as c:
        row = c.execute("insert into public.m2_attempts(user_id, kind, scope, due_at) values (%s, 'quiz', 't', now() + interval '15 minutes') "
                        "returning submitted_at, timed_out, grade, questions, answers", (USER,)).fetchone()
        assert row == (None, False, None, [], {})
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into public.m2_attempts(user_id, kind, scope, due_at) values (%s, 'oral', 't', now() + interval '1 minute')", (USER,))
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into public.m2_attempts(user_id, kind, scope, due_at, grade) values (%s, 'quiz', 't', now() + interval '1 minute', 101)", (USER,))
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into public.m2_attempts(user_id, kind, scope, due_at) values (%s, 'quiz', 't', now() - interval '1 minute')", (USER,))


@pytest.mark.parametrize("role", ["authenticated", "anon"])
def test_browser_roles_cannot_touch_attempts(db, role):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "select * from public.m2_attempts")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "insert into public.m2_attempts(user_id, kind, scope, due_at) values ('11111111-1111-1111-1111-111111111111', 'quiz', 't', now() + interval '1 minute')")


def test_the_server_role_can_use_attempts_and_rls_has_no_policies(db):
    as_role(db, "service_role", "insert into public.m2_attempts(user_id, kind, scope, due_at) values (%s, 'quiz', 'u', now() + interval '1 minute')", OTHER)
    assert as_role(db, "service_role", "select count(*) from public.m2_attempts where user_id = %s", OTHER) == [(1,)]
    with psycopg.connect(db, autocommit=True) as c:
        assert c.execute("select relrowsecurity from pg_class where relname = 'm2_attempts'").fetchone() == (True,)
        assert c.execute("select count(*) from pg_policies where tablename = 'm2_attempts'").fetchone() == (0,)


def test_a_test_has_defaults_limits_and_cascades_with_its_class(db):
    with psycopg.connect(db, autocommit=True) as c:
        cid = _class(c, "מבחן-1")
        row = c.execute("insert into public.m2_tests(class_id, date, lessons, created_by) values (%s, '2026-11-20', '{t,t2}', 't@school.test') "
                        "returning questions, minutes, note, removed_at", (cid,)).fetchone()
        assert row == (12, 45, "", None)
        for column, value in (("questions", 0), ("questions", 41), ("minutes", 4), ("minutes", 181)):
            with pytest.raises(psycopg.errors.CheckViolation):
                c.execute(f"insert into public.m2_tests(class_id, date, lessons, created_by, {column}) values (%s, '2026-11-20', '{{t}}', 't@s', {value})", (cid,))
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("insert into public.m2_tests(class_id, date, lessons, created_by) values (%s, '2026-11-20', '{}', 't@s')", (cid,))
        c.execute("delete from public.m2_classes where id = %s", (cid,))
        assert c.execute("select count(*) from public.m2_tests where class_id = %s", (cid,)).fetchone() == (0,)


@pytest.mark.parametrize("role", ["authenticated", "anon"])
def test_browser_roles_cannot_touch_tests(db, role):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "select * from public.m2_tests")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(db, role, "insert into public.m2_tests(class_id, date, lessons, created_by) values (1, '2026-11-20', '{t}', 'x')")


def test_the_server_role_can_use_tests_and_rls_has_no_policies(db):
    with psycopg.connect(db, autocommit=True) as c:
        cid = _class(c, "מבחן-2")
    as_role(db, "service_role", "insert into public.m2_tests(class_id, date, lessons, created_by) values (%s, '2026-11-21', '{t}', 'x')", cid)
    assert as_role(db, "service_role", "select count(*) from public.m2_tests where class_id = %s", cid) == [(1,)]
    with psycopg.connect(db, autocommit=True) as c:
        assert c.execute("select relrowsecurity from pg_class where relname = 'm2_tests'").fetchone() == (True,)
        assert c.execute("select count(*) from pg_policies where tablename = 'm2_tests'").fetchone() == (0,)
