"""Keeping pictures (add-written-work 1.4): the school year, orphans, the pages of removed assignments, and deleting on request."""
from datetime import date, datetime, timedelta, timezone

import pytest

from mathly2 import cleanup, retention
from mathly2.pictures import MemoryPictures, PictureError, store_picture
from mathly2.store import InMemoryStore

U, V = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
OCT = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)


def test_an_answer_picture_is_kept_until_31_august_of_its_school_year():
    assert retention.expires_on(date(2026, 10, 5)) == date(2027, 8, 31)       # made in October: kept until the next 31 August
    assert retention.expires_on(date(2027, 5, 20)) == date(2027, 8, 31)       # made in May: the same year's 31 August
    assert retention.expires_on(date(2026, 9, 1)) == date(2027, 8, 31) and retention.expires_on(date(2027, 8, 31)) == date(2027, 8, 31)
    assert not retention.is_expired(date(2026, 10, 5), date(2027, 8, 31)) and retention.is_expired(date(2026, 10, 5), date(2027, 9, 1))
    assert retention.is_expired(date(2027, 5, 20), date(2027, 9, 1))


@pytest.fixture
def world():
    store, backend = InMemoryStore(), MemoryPictures()
    return store, backend


def make(store, backend, owner=U, kind="answer", at=OCT):
    return store_picture(store, backend, owner, kind, b"jpeg", at)


def test_an_unreferenced_picture_is_removed_after_a_day_and_a_referenced_or_young_one_stays(world):
    store, backend = world
    a = store.create_assignment(1, "x", date(2026, 11, 20), "t", "quiz", quiz_lesson="t")
    orphan, young, kept = make(store, backend), make(store, backend, at=OCT + timedelta(hours=30)), make(store, backend)
    store.save_submission(a["id"], U, pictures=[kept["id"]])
    got = cleanup.run(store, backend, OCT + timedelta(hours=31))
    assert got == {"orphans": 1, "expired": 0, "removed_assignments": 0}
    assert store.get_picture(orphan["id"])["deleted_at"] is not None and store.get_picture(young["id"])["deleted_at"] is None
    assert store.get_picture(kept["id"])["deleted_at"] is None
    with pytest.raises(PictureError):
        backend.get(orphan["path"])
    assert backend.get(kept["path"]) == b"jpeg" and cleanup.run(store, backend, OCT + timedelta(hours=32))["orphans"] == 0     # nothing left to do


def test_a_picture_a_photo_request_received_counts_as_referenced(world):
    store, backend = world
    a = store.create_assignment(1, "x", date(2026, 11, 20), "t", "quiz", quiz_lesson="t")
    pic = make(store, backend)
    r = store.create_photo_request(U, a["id"], "d", "1234", OCT, OCT + timedelta(minutes=10))
    store.save_photo_request(r["id"], state="received", picture_id=pic["id"])
    assert cleanup.run(store, backend, OCT + timedelta(days=3))["orphans"] == 0


def test_answer_pictures_go_on_1_september_and_the_grade_and_note_stay(world):
    store, backend = world
    a = store.create_assignment(1, "x", date(2026, 11, 20), "t", "quiz", quiz_lesson="t")
    pic = make(store, backend)
    store.save_submission(a["id"], U, pictures=[pic["id"]], state="graded", grade=85, teacher_note="יפה", checked_by="t")
    last_day = datetime(2027, 8, 31, 12, 0, tzinfo=timezone.utc)
    assert cleanup.run(store, backend, last_day)["expired"] == 0
    assert cleanup.run(store, backend, datetime(2027, 9, 1, 12, 0, tzinfo=timezone.utc))["expired"] == 1
    sub = store.get_submission(a["id"], U)
    assert (sub["state"], sub["grade"], sub["teacher_note"]) == ("graded", 85, "יפה") and sub["pictures"] == [pic["id"]]
    assert store.get_picture(pic["id"])["deleted_at"] is not None


def test_assignment_pages_are_not_removed_by_the_end_of_the_year_but_with_their_removed_assignment(world):
    store, backend = world
    page = make(store, backend, owner="t", kind="page")
    a = store.create_assignment(1, "דף", date(2026, 11, 20), "t", "pages", pages=[page["id"]])
    assert cleanup.run(store, backend, datetime(2027, 9, 5, tzinfo=timezone.utc)) == {"orphans": 0, "expired": 0, "removed_assignments": 0}
    store.remove_assignment(a["id"], OCT)
    assert cleanup.run(store, backend, datetime(2027, 9, 6, tzinfo=timezone.utc))["removed_assignments"] == 1
    assert store.get_picture(page["id"])["deleted_at"] is not None


def test_a_failed_delete_leaves_the_picture_for_the_next_run(world):
    store, backend = world
    make(store, backend)

    class Broken(MemoryPictures):
        def delete(self, path):
            raise PictureError(503, "answer_storage_unavailable")
    assert cleanup.run(store, Broken(), OCT + timedelta(days=2)) == {"orphans": 0, "expired": 0, "removed_assignments": 0}
    assert cleanup.run(store, backend, OCT + timedelta(days=2))["orphans"] == 1                 # the next run, with storage back


def test_a_students_answer_pictures_can_be_deleted_early_and_only_theirs_for_those_assignments(world):
    store, backend = world
    a = store.create_assignment(1, "x", date(2026, 11, 20), "t", "quiz", quiz_lesson="t")
    other = store.create_assignment(2, "y", date(2026, 11, 20), "t", "quiz", quiz_lesson="t")
    mine1, mine2, theirs, elsewhere = make(store, backend), make(store, backend), make(store, backend, owner=V), make(store, backend)
    store.save_submission(a["id"], U, pictures=[mine1["id"], mine2["id"]], state="graded", grade=90, teacher_note="יפה")
    store.save_submission(a["id"], V, pictures=[theirs["id"]])
    store.save_submission(other["id"], U, pictures=[elsewhere["id"]])
    assert cleanup.delete_answer_pictures(store, backend, [a["id"]], U, OCT) == 2
    assert all(store.get_picture(p["id"])["deleted_at"] for p in (mine1, mine2))
    assert store.get_picture(theirs["id"])["deleted_at"] is None and store.get_picture(elsewhere["id"])["deleted_at"] is None
    assert store.get_submission(a["id"], U)["grade"] == 90 and cleanup.delete_answer_pictures(store, backend, [a["id"]], U, OCT) == 0


def test_the_hourly_thread_runs_now_keeps_going_after_an_error_and_stops_when_told(world):
    import threading
    store, backend = world
    ran = threading.Event()
    calls = []

    class Flaky(InMemoryStore):
        def pictures(self, *a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("the database is down")
            ran.set()
            return []
    stop = cleanup.start_hourly(Flaky(), backend, every=0.05)
    assert ran.wait(3) and len(calls) >= 2                          # the first run failed; the second still ran
    stop.set()
