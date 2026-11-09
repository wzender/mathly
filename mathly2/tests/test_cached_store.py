from datetime import date

from mathly2.cached import CachedStore
from mathly2.store import InMemoryStore


class Counting(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def classes_taught(self, email):
        self.calls += 1
        return super().classes_taught(email)


def make(seconds=30, now=None):
    base = Counting()
    clock = now or (lambda: 0.0)
    return base, CachedStore(base, seconds, clock=clock)


def test_repeat_read_is_remembered():
    base, store = make()
    store.classes_taught("t@x.com"); store.classes_taught("t@x.com")
    assert base.calls == 1


def test_time_passing_asks_again():
    t = [0.0]
    base, store = make(now=lambda: t[0])
    store.classes_taught("t@x.com"); t[0] = 31
    store.classes_taught("t@x.com")
    assert base.calls == 2


def test_changes_forget():
    base, store = make()
    assert store.classes_taught("t@x.com") == []
    store.create_class("t@x.com", "A", teacher_email="t@x.com")
    assert len(store.classes_taught("t@x.com")) == 1
    cid = store.classes_taught("t@x.com")[0]["id"]
    store.add_member(cid, "s@x.com")
    assert [m["email"] for m in store.members(cid)] == ["s@x.com"]
    store.remove_member(cid, "s@x.com")
    assert store.members(cid) == []
    store.give_role("a@x.com", "teacher", "root")
    assert "teacher" in store.roles_of("a@x.com")
    a = store.create_assignment(cid, "T", date(2030, 1, 1), "t@x.com", "pages", pages=["p1"])
    assert len(store.assignments_of_classes([cid])) == 1
    store.remove_assignment(a["id"])
    assert store.assignments_of_classes([cid]) == []
    store.delete_class(cid)
    assert store.classes_taught("t@x.com") == []


def test_read_started_before_a_change_is_not_kept():
    base, store = make()
    real = base.classes_taught

    def slow(email):
        rows = real(email)
        store.create_class("t@x.com", "B", teacher_email="t@x.com")   # a change lands while this read is running
        return rows
    base.classes_taught = slow
    store.classes_taught("t@x.com")
    base.classes_taught = real
    assert len(store.classes_taught("t@x.com")) == 1


def test_returned_rows_are_copies():
    base, store = make()
    store.create_class("t@x.com", "A", teacher_email="t@x.com")
    store.classes_taught("t@x.com")[0]["name"] = "changed"
    assert store.classes_taught("t@x.com")[0]["name"] == "A"


def test_zero_turns_it_off():
    base, store = make(seconds=0)
    store.classes_taught("t@x.com"); store.classes_taught("t@x.com")
    assert base.calls == 2


def test_progress_writes_do_not_forget():
    base, store = make()
    store.classes_taught("t@x.com")
    store.add_comet("u", "c")
    store.classes_taught("t@x.com")
    assert base.calls == 1


def test_database_times_with_any_number_of_fraction_digits_are_read():
    from datetime import datetime, timezone
    from mathly2.store import _when
    for text in ("2026-11-09T10:10:57.63003+00:00", "2026-11-09T10:10:57.6+00:00", "2026-11-09T10:10:57+00:00", "2026-11-09T10:10:57.630031Z", "2026-11-09T10:10:57.1234567+00:00"):
        assert _when(text).tzinfo is not None
    assert _when("2026-11-09T10:10:57.63003+00:00") == datetime(2026, 11, 9, 10, 10, 57, 630030, tzinfo=timezone.utc)
