import io
import json
import urllib.error

import pytest

from mathly2.store import ClassExists, InMemoryStore, MemberExists, StoreUnavailable, SupabaseStore, TeacherIsStudent


@pytest.fixture
def store():
    return InMemoryStore()



class Recorder(SupabaseStore):
    """SupabaseStore with the network replaced by canned answers; records what it would have sent."""
    def __init__(self, answers):
        super().__init__("https://p.supabase.test", "secret")
        self.answers, self.calls = list(answers), []

    def _request(self, method, table, params=None, body=None, returning=False, upsert=False):
        self.calls.append((method, table, params, body, returning, upsert))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def conflict():
    return urllib.error.HTTPError("u", 409, "conflict", {}, None)



# --- classes, students and roles (rebuild-foundation 2.2, 2.3) ---

def make(store, name="ט'3", **kw):
    return store.create_class("m@x.test", name, lessons=kw.pop("lessons", ["t", "t2"]), **kw)


def test_a_new_class_has_its_lessons_teacher_and_the_ai_off(store):
    row = make(store, teacher_email="t@x.test")
    assert row["lessons"] == ["t", "t2"] and row["teacher_email"] == "t@x.test" and row["created_by"] == "m@x.test"
    assert row["ai_enabled"] is False and row["ai_daily_checks"] == 150 and row["students"] == 0
    assert store.get_class(row["id"])["name"] == "ט'3" and store.get_class(999) is None


def test_class_names_are_unique_across_the_app_ignoring_case(store):
    make(store, "Alef")
    with pytest.raises(ClassExists):
        make(store, "alef")
    with pytest.raises(ClassExists):
        store.create_class("other@x.test", "ALEF", lessons=["t"])        # another creator: still taken


def test_classes_lists_all_and_classes_taught_only_the_teachers(store):
    a = make(store, "A", teacher_email="t1@x.test")["id"]
    make(store, "B", teacher_email="t2@x.test")
    make(store, "C", teacher_email="t1@x.test")
    assert [c["name"] for c in store.classes()] == ["A", "B", "C"]
    assert [c["name"] for c in store.classes_taught("t1@x.test")] == ["A", "C"]
    assert store.classes_taught("nobody@x.test") == [] and a


def test_update_class_changes_only_what_is_given(store):
    cid = make(store, "A", teacher_email="t@x.test")["id"]
    row = store.update_class(cid, name="B", ai_enabled=True, ai_daily_checks=40)
    assert (row["name"], row["ai_enabled"], row["ai_daily_checks"], row["teacher_email"], row["lessons"]) == ("B", True, 40, "t@x.test", ["t", "t2"])
    assert store.update_class(cid, lessons=["k"])["lessons"] == ["k"]
    with pytest.raises(KeyError):
        store.update_class(999, name="x")
    with pytest.raises(ValueError):
        store.update_class(cid, colour="red")


def test_update_class_refuses_a_name_taken_by_another_class(store):
    make(store, "A")
    b = make(store, "B")["id"]
    with pytest.raises(ClassExists):
        store.update_class(b, name="a")
    assert store.update_class(b, name="B")["name"] == "B"                 # its own name is not a clash


def test_a_student_can_be_in_several_classes(store):
    a, b = make(store, "A", lessons=["t"])["id"], make(store, "B", lessons=["t2"])["id"]
    store.add_member(a, "s@x.test")
    store.add_member(b, "s@x.test")
    assert [c["name"] for c in store.classes_of_student("s@x.test")] == ["A", "B"]
    assert store.classes_of_student("s@x.test")[1]["lessons"] == ["t2"]
    with pytest.raises(MemberExists):
        store.add_member(a, "s@x.test")                                   # twice in the same class
    assert store.get_class(a)["students"] == 1


def test_a_teacher_is_never_a_student_of_the_same_class(store):
    cid = make(store, "A", teacher_email="t@x.test")["id"]
    with pytest.raises(TeacherIsStudent):
        store.add_member(cid, "t@x.test")
    store.add_member(cid, "s@x.test")
    with pytest.raises(TeacherIsStudent):
        store.update_class(cid, teacher_email="s@x.test")
    other = make(store, "B")["id"]
    store.add_member(other, "t@x.test")                                   # a student of another class is fine


def test_remove_member_only_from_its_own_class(store):
    a, b = make(store, "A")["id"], make(store, "B")["id"]
    store.add_member(a, "s@x.test")
    assert store.remove_member(b, "s@x.test") is False
    assert store.remove_member(a, "s@x.test") is True
    assert store.classes_of_student("s@x.test") == []


def test_deleting_a_class_removes_its_students_but_not_their_progress(store):
    cid = make(store, "A")["id"]
    store.add_member(cid, "s@x.test")
    store.save_progress("u-1", "skill-1", started_at="t0")
    assert store.delete_class(cid) is True and store.delete_class(cid) is False
    assert store.classes_of_student("s@x.test") == [] and store.get_class(cid) is None
    assert store.get_progress("u-1", "skill-1")["started_at"] == "t0"


def test_link_user_sets_every_entry_of_the_email_once(store):
    a, b = make(store, "A")["id"], make(store, "B")["id"]
    store.add_member(a, "s@x.test")
    store.add_member(b, "s@x.test")
    store.link_user("s@x.test", "u1")
    store.link_user("s@x.test", "u2")
    assert [m["user_id"] for m in store.members(a) + store.members(b)] == ["u1", "u1"]
    store.link_user("nobody@x.test", "u3")                                # no such member: ignored
    c = make(store, "C")["id"]
    store.add_member(c, "s@x.test")
    assert store.members(c)[0]["user_id"] == "u1"                         # a new entry takes the known id


def test_all_students_lists_each_with_their_classes(store):
    a, b = make(store, "A")["id"], make(store, "B")["id"]
    store.add_member(a, "y@x.test")
    store.add_member(b, "y@x.test")
    store.add_member(a, "n@x.test")
    assert store.all_students() == [{"email": "n@x.test", "classes": ["A"]}, {"email": "y@x.test", "classes": ["A", "B"]}]


def test_roles_are_given_once_and_taken_away(store):
    assert store.roles_of("r@x.test") == set()
    store.give_role("r@x.test", "manager", "admin@x.test")
    store.give_role("r@x.test", "manager", "other@x.test")                # idempotent
    store.give_role("r@x.test", "teacher", "admin@x.test")
    assert store.roles_of("r@x.test") == {"manager", "teacher"} and store.roles_of("someone@x.test") == set()
    assert store.take_role("r@x.test", "manager") == "removed"
    assert store.take_role("r@x.test", "manager") == "absent"
    assert store.roles_of("r@x.test") == {"teacher"}


def test_the_last_admin_cannot_be_removed_but_one_of_two_can(store):
    store.give_role("a@x.test", "admin", "s")
    assert store.take_role("a@x.test", "admin") == "last_admin" and store.roles_of("a@x.test") == {"admin"}
    store.give_role("b@x.test", "admin", "s")
    assert store.take_role("a@x.test", "admin") == "removed"
    assert store.take_role("b@x.test", "admin") == "last_admin"


def test_an_admin_named_in_the_settings_counts_as_another_admin(store):
    store.give_role("a@x.test", "admin", "s")
    assert store.take_role("a@x.test", "admin", settings_admins=1) == "removed"


def test_accounts_lists_every_known_email_with_its_given_roles(store):
    cid = make(store, "A", teacher_email="t@x.test")["id"]
    store.add_member(cid, "s@x.test")
    store.give_role("m@x.test", "manager", "a@x.test")
    store.give_role("s@x.test", "teacher", "a@x.test")
    assert store.accounts() == [{"email": "m@x.test", "roles": ["manager"]}, {"email": "s@x.test", "roles": ["teacher"]},
                                {"email": "t@x.test", "roles": []}]


def test_supabase_class_requests_and_parsing():
    row = {"id": 1, "name": "A", "created_by": "m@x.test", "teacher_email": "t@x.test", "lessons": ["t"], "ai_enabled": False,
           "ai_daily_checks": 150, "created_at": "z"}
    counted = {**row, "m2_class_members": [{"count": 3}]}
    s = Recorder([[row], [counted], [counted], [row], [counted]])
    assert s.create_class("m@x.test", "A", lessons=["t"], teacher_email="t@x.test")["students"] == 0
    assert s.get_class(1)["students"] == 3
    assert s.classes_taught("t@x.test")[0]["students"] == 3
    assert s.update_class(1, name="B")["students"] == 3
    create, taught, patch = s.calls[0], s.calls[2], s.calls[3]
    assert create[:2] == ("POST", "m2_classes") and create[3] == {"created_by": "m@x.test", "name": "A", "lessons": ["t"],
        "teacher_email": "t@x.test", "ai_enabled": False, "ai_daily_checks": 150}
    assert taught[2]["teacher_email"] == "eq.t@x.test"
    assert patch[:3] == ("PATCH", "m2_classes", {"id": "eq.1"}) and patch[3] == {"name": "B"}


def test_supabase_student_and_member_requests():
    s = Recorder([[{"m2_classes": {"id": 1, "name": "A", "lessons": ["t"]}}, {"m2_classes": {"id": 2, "name": "B", "lessons": []}}],
                  [{"email": "y@x.test", "m2_classes": {"name": "B"}}, {"email": "y@x.test", "m2_classes": {"name": "A"}}], [{"email": "s@x.test"}], [], None])
    assert [c["name"] for c in s.classes_of_student("s@x.test")] == ["A", "B"]
    assert s.all_students() == [{"email": "y@x.test", "classes": ["A", "B"]}]
    assert s.remove_member(1, "s@x.test") is True and s.remove_member(1, "s@x.test") is False
    s.link_user("s@x.test", "u1")
    assert s.calls[0][2] == {"email": "eq.s@x.test", "select": "m2_classes(id,name,lessons)"}
    assert s.calls[2][2] == {"class_id": "eq.1", "email": "eq.s@x.test"}
    assert s.calls[4][2] == {"email": "eq.s@x.test", "user_id": "is.null"}


def refusal(code, message=""):
    return urllib.error.HTTPError("u", code, "no", {}, io.BytesIO(json.dumps({"message": message}).encode()))


def test_supabase_store_turns_refusals_into_domain_errors():
    with pytest.raises(ClassExists):
        Recorder([conflict()]).create_class("m@x.test", "A")
    with pytest.raises(ClassExists):
        Recorder([conflict()]).update_class(1, name="A")
    with pytest.raises(TeacherIsStudent):
        Recorder([refusal(400, "teacher_is_student")]).update_class(1, teacher_email="s@x.test")
    with pytest.raises(MemberExists):
        Recorder([conflict()]).add_member(1, "s@x.test")
    with pytest.raises(TeacherIsStudent):
        Recorder([refusal(400, "teacher_is_student")]).add_member(1, "t@x.test")
    with pytest.raises(KeyError):
        Recorder([[]]).update_class(1, name="B")


def test_supabase_role_requests():
    s = Recorder([[{"role": "manager"}, {"role": "teacher"}], None, "removed", "last_admin",
                  [{"email": "a@x.test", "role": "admin"}], [{"email": "s@x.test"}], [{"teacher_email": "t@x.test"}]])
    assert s.roles_of("r@x.test") == {"manager", "teacher"}
    s.give_role("r@x.test", "manager", "a@x.test")
    assert s.take_role("r@x.test", "manager") == "removed" and s.take_role("a@x.test", "admin", settings_admins=0) == "last_admin"
    assert [a["email"] for a in s.accounts()] == ["a@x.test", "s@x.test", "t@x.test"]
    give = s.calls[1]
    assert give[:2] == ("POST", "m2_roles") and give[2] == {"on_conflict": "email,role"} and give[3] == {
        "email": "r@x.test", "role": "manager", "granted_by": "a@x.test"} and give[5] is True
    assert s.calls[3][:2] == ("POST", "rpc/m2_take_role") and s.calls[3][3] == {
        "p_email": "a@x.test", "p_role": "admin", "p_settings_admins": 0}


# --- skill learning (tasks 2.2 and 2.3) ---

from datetime import date

U, V = "u-1", "u-2"


def test_progress_starts_empty_and_is_created_on_save(store):
    assert store.get_progress(U, "s1") is None
    row = store.save_progress(U, "s1", started_at="t0")
    assert set(row) == {"user_id", "skill_id", "current_key", "current_helped", "started_at", "mastered_at", "round_start"} and row["round_start"] is None
    assert row["current_helped"] is False and row["started_at"] == "t0" and row["mastered_at"] is None
    assert store.get_progress(U, "s1") == row


def test_saving_progress_changes_only_the_given_fields(store):
    store.save_progress(U, "s1", current_key="s1:abc", started_at="t0")
    store.save_progress(U, "s1", current_helped=True)
    row = store.get_progress(U, "s1")
    assert (row["current_key"], row["current_helped"], row["started_at"]) == ("s1:abc", True, "t0")


def test_progress_rejects_unknown_fields(store):
    with pytest.raises(ValueError):
        store.save_progress(U, "s1", colour="red")
    with pytest.raises(ValueError):
        store.save_progress(U, "s1", stage="practice")                       # the stages are gone


def test_progress_of_lists_only_that_students_rows(store):
    store.save_progress(U, "s1")
    store.save_progress(U, "s2")
    store.save_progress(V, "s1")
    assert sorted(r["skill_id"] for r in store.progress_of(U)) == ["s1", "s2"]
    assert store.progress_of("nobody") == []


def test_returned_progress_is_a_copy(store):
    row = store.save_progress(U, "s1")
    row["current_key"] = "changed"
    assert store.get_progress(U, "s1")["current_key"] is None


def add(store, key, correct, day, counted=True, user=U, skill="s1", mistake=None):
    store.add_answer(user, skill, key, correct, counted, mistake, day)


def test_last_counted_answers_are_oldest_first_and_skip_helped_ones(store):
    d = date(2026, 11, 2)
    add(store, "a", True, d)
    add(store, "b", True, d, counted=False)
    add(store, "c", False, d)
    add(store, "d", True, date(2026, 11, 3))
    got = store.last_counted_answers(U, "s1", 3)
    assert [a["question_key"] for a in got] == ["a", "c", "d"]
    assert [a["correct"] for a in got] == [True, False, True]
    assert got[2]["day"] == date(2026, 11, 3)
    assert [a["question_key"] for a in store.last_counted_answers(U, "s1", 2)] == ["c", "d"]


def test_last_counted_answers_are_per_student_and_skill(store):
    add(store, "a", True, date(2026, 11, 2))
    add(store, "b", True, date(2026, 11, 2), user=V)
    add(store, "c", True, date(2026, 11, 2), skill="s2")
    assert [a["question_key"] for a in store.last_counted_answers(U, "s1", 5)] == ["a"]
    assert store.last_counted_answers("nobody", "s1", 5) == []


def test_answer_counts_include_helped_answers(store):
    d = date(2026, 11, 2)
    add(store, "a", True, d)
    add(store, "a", False, d, counted=False)
    add(store, "b", True, d)
    add(store, "z", True, d, skill="s2")
    assert store.answer_counts(U, "s1") == {"a": 2, "b": 1}
    assert store.answer_counts(U, "none") == {}


def test_daily_correct_counts_correct_answers_per_day_helped_included(store):
    add(store, "a", True, date(2026, 11, 2))
    add(store, "b", True, date(2026, 11, 2), counted=False)
    add(store, "c", False, date(2026, 11, 2))
    add(store, "d", True, date(2026, 11, 3), skill="s2")
    add(store, "e", True, date(2026, 11, 2), user=V)
    assert store.daily_correct(U) == {date(2026, 11, 2): 2, date(2026, 11, 3): 1}
    assert store.daily_correct("nobody") == {}


def test_supabase_progress_requests():
    row = {"user_id": U, "skill_id": "s1", "current_key": "s1:abc"}
    s = Recorder([[row], [row], [row]])
    assert s.get_progress(U, "s1") == row
    assert s.save_progress(U, "s1", current_key="s1:abc") == row
    assert s.progress_of(U) == [row]
    get, save, listing = s.calls
    assert get[:3] == ("GET", "m2_skill_progress", {"user_id": "eq.u-1", "skill_id": "eq.s1", "select": "*"})
    assert save[:2] == ("POST", "m2_skill_progress") and save[2] == {"on_conflict": "user_id,skill_id"}
    assert save[3] == {"user_id": U, "skill_id": "s1", "current_key": "s1:abc"} and save[4:] == (True, True)
    assert listing[2] == {"user_id": "eq.u-1", "select": "*"}


def test_supabase_get_progress_when_there_is_none():
    assert Recorder([[]]).get_progress(U, "s1") is None


def test_supabase_save_progress_rejects_unknown_fields_before_sending():
    s = Recorder([])
    with pytest.raises(ValueError):
        s.save_progress(U, "s1", colour="red")
    assert s.calls == []


def test_supabase_answer_requests_and_parsing():
    s = Recorder([None, [{"question_key": "c", "correct": False, "day": "2026-11-03"},
                         {"question_key": "b", "correct": True, "day": "2026-11-02"}],
                  [{"question_key": "a"}, {"question_key": "a"}, {"question_key": "b"}],
                  [{"day": "2026-11-02", "correct": 2}, {"day": "2026-11-03", "correct": 1}]])
    s.add_answer(U, "s1", "a", True, False, "m1", date(2026, 11, 2))
    got = s.last_counted_answers(U, "s1", 2)
    counts = s.answer_counts(U, "s1")
    daily = s.daily_correct(U)
    assert s.calls[0][:2] == ("POST", "m2_answers")
    assert s.calls[0][3] == {"user_id": U, "skill_id": "s1", "question_key": "a", "correct": True, "counted": False,
                             "mistake_id": "m1", "day": "2026-11-02"}
    assert s.calls[1][2]["counted"] == "eq.true" and s.calls[1][2]["order"] == "id.desc" and s.calls[1][2]["limit"] == "2"
    assert [a["question_key"] for a in got] == ["b", "c"]                      # newest first from the server, returned oldest first
    assert got[0]["day"] == date(2026, 11, 2) and got[1]["correct"] is False
    assert counts == {"a": 2, "b": 1}
    assert s.calls[3][:2] == ("GET", "m2_daily_correct")
    assert daily == {date(2026, 11, 2): 2, date(2026, 11, 3): 1}


def test_a_refusal_that_is_not_a_conflict_is_a_database_problem_not_a_name_clash():
    for call in (lambda s: s.create_class("m@x.test", "A"), lambda s: s.update_class(1, name="A"), lambda s: s.add_member(1, "s@x.test")):
        with pytest.raises(StoreUnavailable, match="supabase refused \\(400\\): column lessons does not exist"):
            call(Recorder([refusal(400, "column lessons does not exist")]))


# --- the next skill and progress dots (add-learning-core 1.3) ---

def test_recent_skills_are_newest_first_each_once_and_include_wrong_and_helped_answers(store):
    d = date(2026, 11, 2)
    add(store, "a", True, d, skill="s1")
    add(store, "b", False, d, skill="s2")
    add(store, "c", True, d, counted=False, skill="s3")
    add(store, "d", True, d, skill="s1")
    assert store.recent_skills(U) == ["s1", "s3", "s2"]
    assert store.recent_skills(U, 2) == ["s1", "s3"]
    assert store.recent_skills("nobody") == []


def test_recent_skills_do_not_include_other_students(store):
    add(store, "a", True, date(2026, 11, 2), skill="s1")
    add(store, "b", True, date(2026, 11, 2), user=V, skill="s2")
    assert store.recent_skills(U) == ["s1"] and store.recent_skills(V) == ["s2"]


def test_solved_keys_are_the_questions_answered_right_at_least_once(store):
    d = date(2026, 11, 2)
    add(store, "a", False, d)
    add(store, "a", True, d)                              # wrong first, right later: solved
    add(store, "b", False, d)                             # only wrong: not solved
    add(store, "c", True, d, counted=False)               # right with help: solved
    add(store, "z", True, d, skill="s2")                  # another skill
    add(store, "y", True, d, user=V)                      # another student
    assert store.solved_keys(U, "s1") == {"a", "c"}
    assert store.solved_keys(U, "none") == set() and store.solved_keys("nobody", "s1") == set()


def test_supabase_recent_skills_and_solved_keys_requests():
    s = Recorder([[{"skill_id": "s1"}, {"skill_id": "s2"}, {"skill_id": "s1"}, {"skill_id": "s3"}],
                  [{"question_key": "a"}, {"question_key": "c"}, {"question_key": "a"}]])
    assert s.recent_skills(U, 2) == ["s1", "s2"]
    assert s.solved_keys(U, "s1") == {"a", "c"}
    recent, solved = s.calls
    assert recent[:2] == ("GET", "m2_answers") and recent[2]["order"] == "id.desc" and recent[2]["user_id"] == "eq.u-1"
    assert solved[2] == {"user_id": "eq.u-1", "skill_id": "eq.s1", "correct": "eq.true", "select": "question_key"}


# --- add-rewards 2.1: last_answered ---

def test_last_answered_is_the_newest_day_per_skill_and_counts_helped_and_wrong_answers(store):
    add(store, "a", True, date(2026, 11, 2))
    add(store, "b", False, date(2026, 11, 5), counted=False)
    add(store, "c", True, date(2026, 11, 3), skill="s2")
    add(store, "d", True, date(2026, 11, 9), user=V)
    assert store.last_answered(U) == {"s1": date(2026, 11, 5), "s2": date(2026, 11, 3)}
    assert store.last_answered("nobody") == {}


def test_supabase_last_answered_reads_the_view_for_one_student():
    s = Recorder([[{"skill_id": "s1", "day": "2026-11-05"}]])
    assert s.last_answered(U) == {"s1": date(2026, 11, 5)}
    method, table, params, *_ = s.calls[0]
    assert (method, table) == ("GET", "m2_last_answered") and params["user_id"] == f"eq.{U}"


# --- add-lesson-quizzes 1.1: timed attempts ---

from datetime import datetime, timedelta, timezone  # noqa: E402

T0 = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
QUESTIONS = [{"skill_id": "s1", "key": "s1:a"}, {"skill_id": "s2", "key": "s2:b"}]


def test_an_attempt_is_created_open_and_read_back(store):
    row = store.create_attempt(U, "quiz", "t", T0, T0 + timedelta(minutes=15), QUESTIONS)
    assert row["submitted_at"] is None and row["grade"] is None and row["timed_out"] is False
    assert row["answers"] == {} and row["questions"] == QUESTIONS and row["due_at"] - row["started_at"] == timedelta(minutes=15)
    assert store.get_attempt(row["id"]) == row and store.get_attempt("nope") is None


def test_saving_answers_and_settling_changes_only_the_named_fields(store):
    row = store.create_attempt(U, "quiz", "t", T0, T0 + timedelta(minutes=15), QUESTIONS)
    store.save_attempt(row["id"], answers={"s1:a": 2})
    saved = store.save_attempt(row["id"], submitted_at=T0 + timedelta(minutes=20), timed_out=True, grade=50)
    assert saved["answers"] == {"s1:a": 2} and saved["grade"] == 50 and saved["timed_out"] is True and saved["submitted_at"] is not None
    assert saved["questions"] == QUESTIONS
    with pytest.raises(ValueError):
        store.save_attempt(row["id"], user_id="someone-else")
    with pytest.raises(KeyError):
        store.save_attempt("missing", grade=1)


def test_a_returned_attempt_is_a_copy(store):
    row = store.create_attempt(U, "quiz", "t", T0, T0 + timedelta(minutes=15), QUESTIONS)
    row["answers"]["x"] = 1
    row["questions"].append({"skill_id": "z", "key": "z"})
    assert store.get_attempt(row["id"])["answers"] == {} and store.get_attempt(row["id"])["questions"] == QUESTIONS


def test_attempts_of_one_student_kind_and_scope_oldest_first(store):
    a = store.create_attempt(U, "quiz", "t", T0, T0 + timedelta(minutes=15), QUESTIONS)
    b = store.create_attempt(U, "quiz", "t", T0 + timedelta(hours=1), T0 + timedelta(hours=1, minutes=15), QUESTIONS)
    store.create_attempt(U, "quiz", "t2", T0, T0 + timedelta(minutes=15), QUESTIONS)
    store.create_attempt(V, "quiz", "t", T0, T0 + timedelta(minutes=15), QUESTIONS)               # another student's
    store.create_attempt(U, "simulation", "t", T0, T0 + timedelta(minutes=15), QUESTIONS)         # another kind
    assert [r["id"] for r in store.attempts_of(U, "quiz", "t")] == [a["id"], b["id"]]
    assert len(store.attempts_of(U, "quiz")) == 3 and store.attempts_of("nobody", "quiz") == []


def test_supabase_attempt_requests():
    row = {"id": "i1", "user_id": U, "kind": "quiz", "scope": "t", "started_at": "2026-11-10T09:00:00+00:00", "due_at": "2026-11-10T09:15:00+00:00",
           "submitted_at": None, "timed_out": False, "grade": None, "questions": QUESTIONS, "answers": {}}
    settled = {**row, "submitted_at": "2026-11-10T09:20:00Z", "timed_out": True, "grade": 50, "answers": {"s1:a": 2}}
    s = Recorder([[row], [row], [], [settled], [row, settled]])
    made = s.create_attempt(U, "quiz", "t", T0, T0 + timedelta(minutes=15), QUESTIONS)
    assert s.calls[0][:2] == ("POST", "m2_attempts") and s.calls[0][3]["due_at"] == "2026-11-10T09:15:00+00:00" and s.calls[0][3]["questions"] == QUESTIONS
    assert made["due_at"] == T0 + timedelta(minutes=15) and made["answers"] == {}                  # real datetimes come back
    assert s.get_attempt("i1")["id"] == "i1" and s.get_attempt("i2") is None
    got = s.save_attempt("i1", submitted_at=T0 + timedelta(minutes=20), timed_out=True, grade=50, answers={"s1:a": 2})
    assert s.calls[3][:3] == ("PATCH", "m2_attempts", {"id": "eq.i1"}) and s.calls[3][3]["submitted_at"] == "2026-11-10T09:20:00+00:00"
    assert got["submitted_at"] == T0 + timedelta(minutes=20) and got["grade"] == 50
    assert len(s.attempts_of(U, "quiz", "t")) == 2
    assert s.calls[4][2] == {"user_id": f"eq.{U}", "kind": "eq.quiz", "select": "*", "order": "started_at", "scope": "eq.t"}


# --- add-test-readiness 1.1: real tests ---

TEST_DAY = date(2026, 11, 20)


def test_a_test_has_the_defaults_and_is_read_back(store):
    row = store.create_test(1, TEST_DAY, ["t", "t2"], "t@x.test")
    assert row["questions"] == 12 and row["minutes"] == 45 and row["note"] == "" and row["removed_at"] is None
    assert row["date"] == TEST_DAY and row["lessons"] == ["t", "t2"] and row["created_by"] == "t@x.test" and row["created_at"].tzinfo
    assert store.get_test(row["id"]) == row and store.get_test(999) is None


def test_a_test_can_be_changed_before_it_is_removed_but_not_after(store):
    row = store.create_test(1, TEST_DAY, ["t"], "t@x.test")
    changed = store.update_test(row["id"], date=date(2026, 11, 22), lessons=["t", "t2"], note="פרק 3", questions=15, minutes=60)
    assert changed["date"] == date(2026, 11, 22) and changed["lessons"] == ["t", "t2"] and changed["note"] == "פרק 3" and changed["questions"] == 15
    with pytest.raises(ValueError):
        store.update_test(row["id"], class_id=2)
    with pytest.raises(KeyError):
        store.update_test(999, note="x")
    assert store.remove_test(row["id"]) is True and store.remove_test(row["id"]) is False
    with pytest.raises(KeyError):
        store.update_test(row["id"], note="y")
    assert store.get_test(row["id"])["removed_at"] is not None                       # still readable: grades keep its name


def test_the_limits_are_enforced(store):
    for bad in ({"questions": 0}, {"questions": 41}, {"minutes": 4}, {"minutes": 181}, {"lessons": []}):
        with pytest.raises(ValueError):
            store.create_test(1, TEST_DAY, bad.get("lessons", ["t"]), "t@x.test", **{k: v for k, v in bad.items() if k != "lessons"})
    row = store.create_test(1, TEST_DAY, ["t"], "t@x.test")
    with pytest.raises(ValueError):
        store.update_test(row["id"], questions=99)


def test_tests_of_classes_are_nearest_first_hide_removed_and_skip_other_classes(store):
    late = store.create_test(1, date(2026, 12, 1), ["t"], "t@x.test")
    soon = store.create_test(1, date(2026, 11, 18), ["t"], "t@x.test")
    other = store.create_test(2, date(2026, 11, 10), ["t"], "t@x.test")
    gone = store.create_test(1, date(2026, 11, 12), ["t"], "t@x.test")
    store.remove_test(gone["id"])
    assert [r["id"] for r in store.tests_of_classes([1])] == [soon["id"], late["id"]]
    assert [r["id"] for r in store.tests_of_classes([1, 2])] == [other["id"], soon["id"], late["id"]]
    assert [r["id"] for r in store.tests_of_classes([1], include_removed=True)] == [gone["id"], soon["id"], late["id"]]
    assert store.tests_of_classes([]) == []


def test_supabase_test_requests():
    row = {"id": 5, "class_id": 1, "date": "2026-11-20", "lessons": ["t"], "note": "", "questions": 12, "minutes": 45, "created_by": "t@x.test",
           "created_at": "2026-11-10T09:00:00+00:00", "removed_at": None}
    s = Recorder([[row], [row], [{**row, "note": "x"}], [], [row], [row]])
    made = s.create_test(1, TEST_DAY, ["t"], "t@x.test", created_at=T0)
    assert s.calls[0][:2] == ("POST", "m2_tests") and s.calls[0][3]["date"] == "2026-11-20" and s.calls[0][3]["created_at"] == T0.isoformat()
    assert made["date"] == TEST_DAY and made["created_at"] == datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
    assert s.get_test(5)["id"] == 5
    assert s.update_test(5, note="x")["note"] == "x" and s.calls[2][2] == {"id": "eq.5", "removed_at": "is.null"}
    with pytest.raises(KeyError):
        s.update_test(5, note="y")
    assert s.remove_test(5) is True and s.calls[4][3]["removed_at"]
    s.tests_of_classes([2, 1])
    assert s.calls[5][2] == {"class_id": "in.(1,2)", "select": "*", "order": "date,id", "removed_at": "is.null"}
    assert s.tests_of_classes([]) == []


def test_answers_of_carries_the_mistake_for_the_round_result(store):
    store.add_answer(U, "s1", "k1", False, True, "m7", date(2026, 11, 2))
    store.add_answer(U, "s1", "k2", True, True, None, date(2026, 11, 2))
    assert [(r["question_key"], r["mistake_id"]) for r in store.answers_of(U, "s1")] == [("k1", "m7"), ("k2", None)]
    assert store.save_progress(U, "s1", round_start=2)["round_start"] == 2
