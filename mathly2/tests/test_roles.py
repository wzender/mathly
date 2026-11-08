from mathly2.access import CACHE_SECONDS, RoleResolver
from mathly2.config import Settings
from mathly2.store import InMemoryStore


def build(**settings):
    store = InMemoryStore()
    return RoleResolver(Settings(**settings), store), store


def test_a_plain_email_is_a_student():
    resolver, _ = build()
    assert resolver.resolve("kid@x.test") == {"student"}


def test_emails_are_compared_ignoring_case_and_spaces():
    resolver, _ = build(developers=frozenset({"dev@x.test"}))
    assert "developer" in resolver.resolve("  Dev@X.test ")


def test_a_developer_from_the_settings():
    resolver, _ = build(developers=frozenset({"dev@x.test"}))
    assert resolver.resolve("dev@x.test") == {"developer"}


def test_a_developer_row_in_the_table_is_ignored():
    resolver, store = build()
    store.give_role("sneaky@x.test", "developer", "someone")
    assert resolver.resolve("sneaky@x.test") == {"student"}


def test_a_teacher_from_the_settings_and_a_class_teacher_who_is_in_no_setting():
    resolver, store = build(teachers=frozenset({"listed@x.test"}))
    store.create_class("m@x.test", "A", lessons=["t"], teacher_email="classteacher@x.test")
    assert resolver.resolve("listed@x.test") == {"teacher"}
    assert resolver.resolve("classteacher@x.test") == {"teacher"}


def test_roles_given_in_the_table():
    resolver, store = build()
    for role in ("manager", "admin", "teacher", "student"):
        store.give_role(f"{role}@x.test", role, "a@x.test")
    assert [sorted(resolver.resolve(f"{r}@x.test")) for r in ("manager", "admin", "teacher", "student")] == [["manager"], ["admin"], ["teacher"], ["student"]]


def test_first_admins_from_the_settings():
    resolver, _ = build(admins=frozenset({"head@x.test"}))
    assert resolver.resolve("head@x.test") == {"admin"}


def test_a_student_of_a_class_is_a_student_and_a_manager_without_a_class_is_not():
    resolver, store = build()
    cid = store.create_class("m@x.test", "A", lessons=["t"])["id"]
    store.add_member(cid, "kid@x.test")
    store.give_role("boss@x.test", "manager", "a@x.test")
    assert resolver.resolve("kid@x.test") == {"student"}
    assert resolver.resolve("boss@x.test") == {"manager"}           # no class, so no student role


def test_several_roles_at_once():
    resolver, store = build(teachers=frozenset({"multi@x.test"}))
    cid = store.create_class("m@x.test", "A", lessons=["t"])["id"]
    store.add_member(cid, "multi@x.test")
    store.give_role("multi@x.test", "manager", "a@x.test")
    assert resolver.resolve("multi@x.test") == {"teacher", "manager", "student"}


def test_roles_are_cached_for_a_while_and_a_change_shows_after_it():
    now = [0.0]
    store = InMemoryStore()
    resolver = RoleResolver(Settings(), store, clock=lambda: now[0])
    assert resolver.resolve("r@x.test") == {"student"}
    store.give_role("r@x.test", "manager", "a@x.test")
    assert resolver.resolve("r@x.test") == {"student"}               # still the cached answer
    now[0] = CACHE_SECONDS + 1
    assert resolver.resolve("r@x.test") == {"manager"}


def test_forgetting_one_email_or_all_applies_a_change_at_once():
    resolver, store = build()
    resolver.resolve("r@x.test"); resolver.resolve("s@x.test")
    store.give_role("r@x.test", "manager", "a@x.test"); store.give_role("s@x.test", "admin", "a@x.test")
    resolver.forget("R@x.test")
    assert resolver.resolve("r@x.test") == {"manager"} and resolver.resolve("s@x.test") == {"student"}
    resolver.forget()
    assert resolver.resolve("s@x.test") == {"admin"}


def test_the_cache_lasts_thirty_seconds():
    assert CACHE_SECONDS == 30
