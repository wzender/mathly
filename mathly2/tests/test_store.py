import urllib.error

import pytest

from mathly2.store import ClassExists, InMemoryStore, MemberExists, SupabaseStore


@pytest.fixture
def store():
    return InMemoryStore()


def test_classes_belong_to_their_teacher(store):
    a = store.create_class("t1@x.test", "ט'3")
    store.create_class("t2@x.test", "ח'1")
    assert [c["name"] for c in store.classes_of("t1@x.test")] == ["ט'3"]
    assert store.get_class(a["id"])["teacher_email"] == "t1@x.test"
    assert store.get_class(999) is None


def test_class_names_are_unique_per_teacher_ignoring_case(store):
    store.create_class("t@x.test", "Alef")
    with pytest.raises(ClassExists):
        store.create_class("t@x.test", "alef")
    store.create_class("other@x.test", "Alef")


def test_a_student_belongs_to_one_class(store):
    a, b = store.create_class("t@x.test", "A")["id"], store.create_class("t@x.test", "B")["id"]
    store.add_member(a, "s@x.test")
    with pytest.raises(MemberExists):
        store.add_member(b, "s@x.test")
    assert store.membership("s@x.test")["class_name"] == "A"
    assert store.classes_of("t@x.test")[0]["students"] == 1


def test_remove_member_only_from_its_own_class(store):
    a, b = store.create_class("t@x.test", "A")["id"], store.create_class("t@x.test", "B")["id"]
    store.add_member(a, "s@x.test")
    assert store.remove_member(b, "s@x.test") is False
    assert store.remove_member(a, "s@x.test") is True
    assert store.membership("s@x.test") is None


def test_link_user_sets_it_once(store):
    a = store.create_class("t@x.test", "A")["id"]
    store.add_member(a, "s@x.test")
    store.link_user("s@x.test", "u1")
    store.link_user("s@x.test", "u2")
    assert store.membership("s@x.test")["user_id"] == "u1"
    store.link_user("nobody@x.test", "u3")   # no such member: ignored


class Recorder(SupabaseStore):
    """SupabaseStore with the network replaced by canned answers; records what it would have sent."""
    def __init__(self, answers):
        super().__init__("https://p.supabase.test", "secret")
        self.answers, self.calls = list(answers), []

    def _request(self, method, table, params=None, body=None, returning=False):
        self.calls.append((method, table, params, body, returning))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def conflict():
    return urllib.error.HTTPError("u", 409, "conflict", {}, None)


def test_supabase_store_requests():
    s = Recorder([[{"id": 1, "name": "A", "teacher_email": "t@x.test", "created_at": "z"}],
                  [{"id": 1, "name": "A", "teacher_email": "t@x.test", "created_at": "z", "m2_class_members": [{"count": 3}]}],
                  [{"class_id": 1, "email": "s@x.test", "user_id": None, "added_at": "z", "m2_classes": {"name": "A"}}],
                  [{"email": "s@x.test"}], []])
    assert s.create_class("t@x.test", "A")["id"] == 1
    assert s.classes_of("t@x.test")[0]["students"] == 3
    assert s.membership("s@x.test")["class_name"] == "A"
    assert s.remove_member(1, "s@x.test") is True
    assert s.remove_member(1, "s@x.test") is False
    assert s.calls[0][:2] == ("POST", "m2_classes") and s.calls[0][3] == {"teacher_email": "t@x.test", "name": "A"}
    assert s.calls[3][2] == {"class_id": "eq.1", "email": "eq.s@x.test"}


def test_supabase_store_turns_conflicts_into_domain_errors():
    with pytest.raises(ClassExists):
        Recorder([conflict()]).create_class("t@x.test", "A")
    with pytest.raises(MemberExists):
        Recorder([conflict()]).add_member(1, "s@x.test")


def test_supabase_link_only_fills_an_empty_user_id():
    s = Recorder([None])
    s.link_user("s@x.test", "u1")
    assert s.calls[0][2] == {"email": "eq.s@x.test", "user_id": "is.null"}
