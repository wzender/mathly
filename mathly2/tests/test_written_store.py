"""The store for written work (add-written-work 1.1 and 1.2): pictures, assignments, submissions, photo requests, push subscriptions."""
from datetime import date, datetime, timedelta, timezone

import pytest

from mathly2.store import InMemoryStore
from mathly2.tests.test_store import Recorder

U, V = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
NOW = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
DUE = date(2026, 11, 20)


@pytest.fixture
def store():
    return InMemoryStore()


def picture(store, owner=U, kind="answer", path=None):
    return store.create_picture(owner, kind, path or f"{owner}/{len(store.pictures(include_deleted=True))}.jpg", "image/jpeg", 1000, NOW)


# --- 1.1 pictures ---

def test_a_picture_is_created_read_and_marked_deleted_once(store):
    row = picture(store)
    assert row["deleted_at"] is None and row["kind"] == "answer" and store.get_picture(row["id"]) == row and store.get_picture("nope") is None
    assert store.mark_picture_deleted(row["id"], NOW) is True and store.mark_picture_deleted(row["id"]) is False
    assert store.get_picture(row["id"])["deleted_at"] == NOW
    with pytest.raises(ValueError):
        store.create_picture(U, "scan", "x", "image/jpeg", 1)


def test_pictures_list_by_kind_and_owner_and_hide_deleted(store):
    a, b, page = picture(store), picture(store, owner=V), picture(store, kind="page")
    store.mark_picture_deleted(b["id"])
    assert [p["id"] for p in store.pictures()] == [a["id"], page["id"]]
    assert [p["id"] for p in store.pictures(kind="page")] == [page["id"]] and [p["id"] for p in store.pictures(owner_id=U)] == [a["id"], page["id"]]
    assert len(store.pictures(include_deleted=True)) == 3


def test_picture_refs_find_assignments_submissions_and_requests(store):
    pic, lone = picture(store, kind="page"), picture(store)
    a = store.create_assignment(1, "דף", DUE, "t@x.test", "pages", pages=[pic["id"]])
    s = store.save_submission(a["id"], U, pictures=[lone["id"]])
    r = store.create_photo_request(U, a["id"], "d1", "1234", NOW, NOW + timedelta(minutes=10))
    store.save_photo_request(r["id"], state="received", picture_id=lone["id"])
    assert store.picture_refs(pic["id"]) == {"assignments": [a["id"]], "submissions": [], "requests": []}
    assert store.picture_refs(lone["id"]) == {"assignments": [], "submissions": [s["id"]], "requests": [r["id"]]}
    assert store.picture_refs(picture(store)["id"]) == {"assignments": [], "submissions": [], "requests": []}


# --- 1.1 assignments ---

def test_an_assignment_needs_a_title_and_its_content(store):
    page = picture(store, kind="page")
    ok = store.create_assignment(1, "דף עבודה", DUE, "t@x.test", "pages", note="הערה", pages=[page["id"]])
    assert ok["pages"] == [page["id"]] and ok["note"] == "הערה" and ok["removed_at"] is None and store.get_assignment(ok["id"]) == ok
    quiz = store.create_assignment(1, "בוחן כתוב", DUE, "t@x.test", "quiz", quiz_lesson="t")
    exam = store.create_assignment(1, "מבחן תרגול", DUE, "t@x.test", "exercise_test", test_id=5, exercise_number=1)
    assert quiz["quiz_lesson"] == "t" and exam["exercise_number"] == 1
    for bad in (dict(kind="pages"), dict(kind="quiz"), dict(kind="exercise_test", test_id=5), dict(kind="exercise_test", test_id=5, exercise_number=3), dict(kind="video")):
        with pytest.raises(ValueError):
            store.create_assignment(1, "x", DUE, "t", **bad)
    with pytest.raises(ValueError):
        store.create_assignment(1, "", DUE, "t", "quiz", quiz_lesson="t")


def test_assignments_of_classes_nearest_due_first_and_removal_hides_but_keeps(store):
    late = store.create_assignment(1, "מאוחר", date(2026, 12, 1), "t", "quiz", quiz_lesson="t")
    soon = store.create_assignment(1, "קרוב", date(2026, 11, 14), "t", "quiz", quiz_lesson="t")
    other = store.create_assignment(2, "אחרת", date(2026, 11, 1), "t", "quiz", quiz_lesson="t")
    assert [a["id"] for a in store.assignments_of_classes([1])] == [soon["id"], late["id"]]
    assert store.remove_assignment(soon["id"], NOW) is True and store.remove_assignment(soon["id"]) is False
    assert [a["id"] for a in store.assignments_of_classes([1, 2])] == [other["id"], late["id"]]
    assert [a["id"] for a in store.assignments_of_classes([1], include_removed=True)] == [soon["id"], late["id"]] and store.assignments_of_classes([]) == []


# --- 1.1 submissions ---

def test_a_submission_is_one_per_student_and_assignment_and_is_rewritten(store):
    a = store.create_assignment(1, "x", DUE, "t", "quiz", quiz_lesson="t")
    first = store.save_submission(a["id"], U, pictures=["p1"], handed_at=NOW)
    assert first["state"] == "handed_in" and first["grade"] is None and first["late"] is False and first["pictures"] == ["p1"]
    again = store.save_submission(a["id"], U, pictures=["p2", "p3"], handed_at=NOW + timedelta(hours=1), late=True)
    assert again["id"] == first["id"] and again["pictures"] == ["p2", "p3"] and again["late"] is True
    assert store.get_submission(a["id"], U) == again and store.get_submission(a["id"], V) is None and store.get_submission_by_id(again["id"]) == again
    assert store.save_submission(a["id"], V)["id"] != first["id"]


def test_checking_a_submission_sets_grade_note_and_who(store):
    a = store.create_assignment(1, "x", DUE, "t", "quiz", quiz_lesson="t")
    store.save_submission(a["id"], U, pictures=["p1"])
    graded = store.save_submission(a["id"], U, state="graded", grade=85, teacher_note="יפה", checked_at=NOW, checked_by="t@x.test")
    assert (graded["state"], graded["grade"], graded["teacher_note"], graded["checked_by"]) == ("graded", 85, "יפה", "t@x.test") and graded["checked_at"] == NOW
    returned = store.save_submission(a["id"], U, state="returned", teacher_note="חסר נימוק", grade=None)
    assert returned["state"] == "returned" and returned["grade"] is None
    with pytest.raises(ValueError):
        store.save_submission(a["id"], V, state="graded")                                  # a grade is required
    with pytest.raises(ValueError):
        store.save_submission(a["id"], U, owner="x")
    with pytest.raises(ValueError):
        store.save_submission(a["id"], U, grade=101)
    assert store.get_submission(a["id"], V) is None                                          # a refused write stores nothing


def test_submissions_of_assignments_oldest_first_and_of_a_user(store):
    a = store.create_assignment(1, "x", DUE, "t", "quiz", quiz_lesson="t")
    b = store.create_assignment(1, "y", DUE, "t", "quiz", quiz_lesson="t")
    later = store.save_submission(a["id"], V, handed_at=NOW + timedelta(days=1))
    earlier = store.save_submission(a["id"], U, handed_at=NOW)
    mine_b = store.save_submission(b["id"], U, handed_at=NOW + timedelta(hours=2))
    assert [s["id"] for s in store.submissions_of_assignments([a["id"]])] == [earlier["id"], later["id"]]
    assert [s["id"] for s in store.submissions_of_assignments([a["id"], b["id"]])] == [earlier["id"], mine_b["id"], later["id"]]
    assert {s["id"] for s in store.submissions_of_user(U)} == {earlier["id"], mine_b["id"]} and store.submissions_of_assignments([]) == []


# --- 1.2 photo requests ---

def test_a_photo_request_waits_and_a_newer_one_supersedes_the_older_for_the_same_assignment(store):
    a = store.create_assignment(1, "x", DUE, "t", "quiz", quiz_lesson="t")
    b = store.create_assignment(1, "y", DUE, "t", "quiz", quiz_lesson="t")
    first = store.create_photo_request(U, a["id"], "laptop", "4821", NOW, NOW + timedelta(minutes=10))
    other = store.create_photo_request(U, b["id"], "laptop", "1111", NOW, NOW + timedelta(minutes=10))
    second = store.create_photo_request(U, a["id"], "laptop", "9090", NOW + timedelta(minutes=1), NOW + timedelta(minutes=11))
    assert first["state"] == "waiting" and first["picture_id"] is None and first["code"] == "4821"
    assert store.get_photo_request(first["id"])["state"] == "superseded" and store.get_photo_request(second["id"])["state"] == "waiting"
    assert store.get_photo_request(other["id"])["state"] == "waiting"                      # another assignment's request is not replaced
    assert [r["id"] for r in store.open_photo_requests(U)] == [second["id"], other["id"]] and store.open_photo_requests(V) == []


def test_a_photo_request_moves_through_its_states_and_leaves_the_open_list(store):
    a = store.create_assignment(1, "x", DUE, "t", "quiz", quiz_lesson="t")
    pic = picture(store)
    r = store.create_photo_request(U, a["id"], "laptop", "0042", NOW, NOW + timedelta(minutes=10))
    assert store.save_photo_request(r["id"], state="uploading")["state"] == "uploading" and len(store.open_photo_requests(U)) == 1
    done = store.save_photo_request(r["id"], state="received", picture_id=pic["id"])
    assert done["picture_id"] == pic["id"] and store.open_photo_requests(U) == []
    with pytest.raises(ValueError):
        store.save_photo_request(r["id"], user_id=V)
    with pytest.raises(KeyError):
        store.save_photo_request("missing", state="failed")
    assert store.get_photo_request("missing") is None


# --- 1.2 push subscriptions ---

def test_push_subscriptions_are_per_endpoint_deletable_and_dropped_when_the_key_changes(store):
    a = store.add_push_subscription(U, "https://push/1", "p", "a", "key-A")
    store.add_push_subscription(U, "https://push/2", "p", "a", "key-A")
    store.add_push_subscription(V, "https://push/3", "p", "a", "key-B")
    assert store.add_push_subscription(U, "https://push/1", "p2", "a2", "key-A")["id"] == a["id"]            # the same phone again: one row
    assert {s["endpoint"] for s in store.push_subscriptions_of(U)} == {"https://push/1", "https://push/2"} and store.push_subscriptions_of("nobody") == []
    assert store.delete_push_subscription("https://push/2") is True and store.delete_push_subscription("https://push/2") is False
    assert store.drop_push_subscriptions_not_of("key-A") == 1                                                # V's was made under another key
    assert [s["endpoint"] for s in store.push_subscriptions_of(U)] == ["https://push/1"] and store.push_subscriptions_of(V) == []


# --- the Supabase store: what it asks the database ---

def test_supabase_requests_for_pictures_and_assignments():
    pic = {"id": "p1", "owner_id": U, "kind": "answer", "path": "u/1.jpg", "content_type": "image/jpeg", "size": 10, "created_at": "2026-11-12T09:00:00+00:00", "deleted_at": None}
    asg = {"id": 3, "class_id": 1, "title": "x", "note": "", "due_date": "2026-11-20", "kind": "pages", "pages": ["p1"], "quiz_lesson": None, "test_id": None,
           "exercise_number": None, "created_by": "t", "created_at": "2026-11-12T09:00:00+00:00", "removed_at": None}
    s = Recorder([[pic], [pic], [pic], [{**pic, "deleted_at": "x"}], [asg], [asg], [asg], [{"id": 3}], [{"id": 9}], [{"id": 4}]])
    made = s.create_picture(U, "answer", "u/1.jpg", "image/jpeg", 10, NOW)
    assert s.calls[0][:2] == ("POST", "m2_pictures") and s.calls[0][3]["created_at"] == NOW.isoformat() and made["created_at"] == NOW
    assert s.get_picture("p1")["id"] == "p1" and [p["id"] for p in s.pictures(kind="answer", owner_id=U)] == ["p1"]
    assert s.calls[2][2] == {"select": "*", "order": "created_at", "kind": "eq.answer", "owner_id": f"eq.{U}", "deleted_at": "is.null"}
    assert s.mark_picture_deleted("p1", NOW) is True and s.calls[3][2] == {"id": "eq.p1", "deleted_at": "is.null"}
    made_a = s.create_assignment(1, "x", DUE, "t", "pages", pages=["p1"])
    assert s.calls[4][3]["due_date"] == "2026-11-20" and s.calls[4][3]["pages"] == ["p1"] and made_a["due_date"] == DUE
    assert s.get_assignment(3)["pages"] == ["p1"] and [a["id"] for a in s.assignments_of_classes([2, 1])] == [3]
    assert s.calls[6][2] == {"class_id": "in.(1,2)", "select": "*", "order": "due_date,id", "removed_at": "is.null"}
    s2 = Recorder([[{"id": 3}], [{"id": 9}], [{"id": 4}]])
    assert s2.picture_refs("p1") == {"assignments": [3], "submissions": [9], "requests": [4]}
    assert s2.calls[0][2] == {"pages": "cs.{p1}", "select": "id"} and s2.calls[1][2] == {"pictures": "cs.{p1}", "select": "id"}


def test_supabase_requests_for_submissions_requests_and_push():
    sub = {"id": 7, "assignment_id": 3, "user_id": U, "pictures": ["p1"], "state": "handed_in", "late": False, "handed_at": "2026-11-12T09:00:00+00:00",
           "grade": None, "teacher_note": "", "checked_at": None, "checked_by": None}
    req = {"id": "r1", "user_id": U, "assignment_id": 3, "device": "d", "code": "1234", "state": "waiting", "created_at": "2026-11-12T09:00:00+00:00",
           "expires_at": "2026-11-12T09:10:00+00:00", "picture_id": None}
    s = Recorder([[sub], [sub], [sub], [req], [req], [req], [req], [{"id": 1, "endpoint": "e", "created_at": "2026-11-12T09:00:00+00:00"}], [{"id": 1}], [{"id": 1}, {"id": 2}]])
    saved = s.save_submission(3, U, pictures=["p1", "p2"], state="graded", grade=80, checked_at=NOW)
    assert s.calls[0][:3] == ("POST", "m2_submissions", {"on_conflict": "assignment_id,user_id"}) and s.calls[0][5] is True
    assert s.calls[0][3]["pictures"] == ["p1", "p2"] and s.calls[0][3]["checked_at"] == NOW.isoformat() and saved["handed_at"] == NOW
    assert s.get_submission(3, U)["id"] == 7 and s.get_submission_by_id(7)["id"] == 7
    s.create_photo_request(U, 3, "d", "1234", NOW, NOW + timedelta(minutes=10))
    assert s.calls[3][:2] == ("PATCH", "m2_photo_requests") and s.calls[3][2]["state"] == "eq.waiting" and s.calls[3][3] == {"state": "superseded"}
    assert s.calls[4][:2] == ("POST", "m2_photo_requests") and s.calls[4][3]["expires_at"] == (NOW + timedelta(minutes=10)).isoformat()
    assert s.save_photo_request("r1", state="received", picture_id="p1")["id"] == "r1"
    assert s.open_photo_requests(U)[0]["id"] == "r1" and s.calls[6][2]["state"] == "in.(waiting,uploading)"
    s.add_push_subscription(U, "e", "p", "a", "k")
    assert s.calls[7][:3] == ("POST", "m2_push_subscriptions", {"on_conflict": "endpoint"}) and s.calls[7][5] is True
    assert s.delete_push_subscription("e") is True and s.drop_push_subscriptions_not_of("k") == 2
    assert s.calls[9][:3] == ("DELETE", "m2_push_subscriptions", {"key_id": "neq.k"})
