"""The bank with lessons kept in the database (add-subjects-and-worksheets 2.1-2.3): merging, order, checks and stable ids."""
import pytest

from mathly2.bank import Bank, BankError, MATH, lesson_problems, load_bank, merge, question_key

SCIENCE = {"id": "science", "name": "מדעים", "icon": "⚗"}


def question(text, right="נכון", wrong=("לא נכון",), mistake="w{n}_m1"):
    return {"question": text, "source": "sheet",
            "choices": [{"text": right, "correct": True}] + [{"text": w, "mistake": mistake} for w in wrong]}


def document(n, name="תאים", skills=1, per_skill=5):
    return {"name": name, "next_skill": skills + 1, "next_mistake": 2,
            "mistakes": {f"w{n}_m1": {"name": "בלבול", "tip": "קראו שוב"}},
            "skills": [{"id": f"w{n}_{k}", "name": f"מיומנות {k}", "questions": [
                {**question(f"שאלה {k}.{q}"), "choices": [{"text": "נכון", "correct": True}, {"text": "לא", "mistake": f"w{n}_m1"}]}
                for q in range(per_skill)]} for k in range(1, skills + 1)]}


def row(n, subject="science", position=1, doc=None):
    return {"id": n, "subject_id": subject, "position": position, "published": doc if doc is not None else document(n)}


@pytest.fixture(scope="module")
def file_data():
    return load_bank().data


def test_published_lessons_follow_the_math_file_in_subject_then_position_order(file_data):
    merged = Bank(merge(file_data, [MATH, SCIENCE], [row(9, position=2, doc=document(9, "חומרים")), row(4, position=1), row(5, subject="math")]))
    ids = [u["id"] for u in merged.lessons]
    math_file = [u["id"] for u in file_data["units"]]
    assert ids[:len(math_file)] == math_file                                      # the file's lessons first, in its order
    assert ids[len(math_file):] == ["w5", "w4", "w9"]                              # then math's added lesson, then science by position
    assert merged.subject_of_lesson("w4") == "science" and merged.subject_of_lesson(math_file[0]) == "math"
    assert [u["id"] for u in merged.lessons_of_subject("science")] == ["w4", "w9"]
    assert merged.subject_of_skill("w4_1") == "science"
    assert [s["id"] for s in merged.subjects] == ["math", "science"]


def test_a_published_lesson_works_like_a_math_lesson(file_data):
    merged = Bank(merge(file_data, [MATH, SCIENCE], [row(4)]))
    key = merged.question_keys("w4_1")[0]
    served = merged.practice_question("w4_1", key)
    assert "correct" not in str(served) and "mistake" not in str(served) and "source" not in str(served)
    assert merged.grade("w4_1", key, 0) == {"correct": True, "mistake": None}
    assert merged.grade("w4_1", key, 1)["mistake"]["name"] == "בלבול"


def test_the_source_label_does_not_change_a_questions_key(file_data):
    doc = document(4)
    relabeled = document(4)
    relabeled["skills"][0]["questions"][0]["source"] = "person"
    keys = lambda d: Bank(merge(file_data, [MATH, SCIENCE], [row(4, doc=d)])).question_keys("w4_1")
    assert keys(doc) == keys(relabeled)


def test_a_broken_database_lesson_is_left_out_and_logged_and_the_rest_load(file_data):
    broken = document(6)
    broken["skills"][0]["questions"][0]["choices"][1]["correct"] = True             # two right answers
    logged = []
    merged = Bank(merge(file_data, [MATH, SCIENCE], [row(4), row(6, position=2, doc=broken), row(8, subject="gone")], log=logged.append))
    assert [u["id"] for u in merged.lessons_of_subject("science")] == ["w4"]
    assert any("lesson 6" in m and "2 correct choices" in m for m in logged)
    assert any("lesson 8" in m and "subject does not exist" in m for m in logged)


def test_lesson_problems_name_what_is_wrong():
    assert lesson_problems(document(4), 4) == []
    assert lesson_problems({"name": "", "skills": [], "mistakes": {}}, 4) == ["the lesson has no name"]
    stolen = document(4)
    stolen["skills"][0]["id"] = "t_ext"                                             # an id that is not this lesson's
    assert any("t_ext" in p for p in lesson_problems(stolen, 4))
    unknown = document(4)
    unknown["skills"][0]["questions"][0]["choices"][1]["mistake"] = "w4_m9"
    assert any("unknown mistake 'w4_m9'" in p for p in lesson_problems(unknown, 4))


def test_a_broken_content_file_still_stops_the_server(tmp_path):
    bad = tmp_path / "bank.json"
    bad.write_text('{"units": [], "skills": [{"id": "s", "unit": "nowhere", "questions": []}], "mistakes": {}}', encoding="utf-8")
    with pytest.raises(BankError):
        load_bank(bad)


def test_no_subjects_given_means_math_only(file_data):
    assert Bank(merge(file_data, [], [])).subjects == [MATH]


def test_deleting_a_skill_keeps_the_other_ids_and_their_question_keys(file_data):
    doc = document(4, skills=3)
    before = Bank(merge(file_data, [MATH, SCIENCE], [row(4, doc=doc)]))
    key3 = before.question_keys("w4_3")[0]
    del doc["skills"][1]                                                            # w4_2 goes; w4_1 and w4_3 stay as they were
    after = Bank(merge(file_data, [MATH, SCIENCE], [row(4, doc=doc)]))
    assert [s["id"] for s in after.skills if s["unit"] == "w4"] == ["w4_1", "w4_3"]
    assert after.question_keys("w4_3")[0] == key3 == question_key("w4_3", {k: v for k, v in doc["skills"][1]["questions"][0].items() if k != "source"})


# ---- the served bank: built at start-up and swapped after a change (2.2) ----

from mathly2 import content                                     # noqa: E402
from mathly2.config import Settings                             # noqa: E402
from mathly2.main import create_app                             # noqa: E402
from mathly2.store import InMemoryStore, StoreUnavailable       # noqa: E402


def test_a_published_lesson_is_served_after_a_rebuild_without_a_restart():
    store = InMemoryStore()
    app = create_app(Settings(), store=store)
    before = app.state.bank
    store.create_subject("science", "מדעים", "m@x.test")
    lesson = store.create_lesson("science", "m@x.test", {})
    store.save_lesson(lesson["id"], published=document(lesson["id"]))
    assert app.state.bank.lessons_of_subject("science") == []                     # nothing changes until the rebuild
    content.rebuild(app)
    assert [u["id"] for u in app.state.bank.lessons_of_subject("science")] == [f"w{lesson['id']}"]
    assert before.lessons_of_subject("science") == []                              # a request holding the old bank keeps it


def test_a_failed_build_keeps_the_bank_already_served(monkeypatch):
    app = create_app(Settings(), store=InMemoryStore())
    served = app.state.bank
    def broken(*a, **kw):
        raise RuntimeError("cannot build")
    monkeypatch.setattr(content, "merge", broken)
    with pytest.raises(RuntimeError):
        content.rebuild(app)
    assert app.state.bank is served


class NoSubjectTables(InMemoryStore):
    def subjects(self):
        raise StoreUnavailable("supabase answered 404 for GET m2_subjects")


def test_without_the_migration_the_app_starts_and_serves_the_content_file_only():
    app = create_app(Settings(), store=NoSubjectTables())
    assert [s["id"] for s in app.state.bank.subjects] == ["math"]
    assert len(app.state.bank.lessons) == len(app.state.base_bank.lessons)
    assert "m2_subjects" in app.state.content_error


# ---- ids made by the server (2.3) ----

from mathly2.lessons import assign_ids                          # noqa: E402


def test_new_skills_and_mistakes_get_ids_of_the_lesson_and_choices_follow_the_rename():
    doc = {"name": "תאים", "mistakes": {"tmp": {"name": "בלבול", "tip": "x"}},
           "skills": [{"name": "א", "questions": [{"question": "?", "choices": [{"text": "1", "correct": True}, {"text": "2", "mistake": "tmp"}]}]},
                      {"id": "made-up", "name": "ב", "questions": []}]}
    got = assign_ids(doc, 7)
    assert [s["id"] for s in got["skills"]] == ["w7_1", "w7_2"] and list(got["mistakes"]) == ["w7_m1"]
    assert got["skills"][0]["questions"][0]["choices"][1]["mistake"] == "w7_m1"
    assert got["next_skill"] == 3 and got["next_mistake"] == 2
    assert doc["skills"][0].get("id") is None                                       # the input is not changed


def test_an_id_is_never_reused_after_a_delete_and_a_reorder_changes_none():
    doc = assign_ids({"name": "x", "mistakes": {}, "skills": [{"name": "א"}, {"name": "ב"}, {"name": "ג"}]}, 7)
    del doc["skills"][2]                                                           # w7_3 deleted
    doc["skills"].reverse()                                                        # w7_2, w7_1
    doc["skills"].append({"name": "ד"})
    again = assign_ids(doc, 7)
    assert [s["id"] for s in again["skills"]] == ["w7_2", "w7_1", "w7_4"]           # w7_3 is not given again


def test_mastery_and_review_survive_a_reorder_of_skills(file_data):
    from datetime import date
    store = InMemoryStore()
    doc = assign_ids(document(7, skills=2), 7)
    store.save_progress("u1", "w7_2", started_at="then", mastered_at="then")
    store.add_review("u1", [("w7_2", "k", "practice")], date(2026, 11, 11))
    doc["skills"].reverse()
    bank = Bank(merge(file_data, [MATH, SCIENCE], [row(7, doc=doc)]))
    assert [s["id"] for s in bank.skills if s["unit"] == "w7"] == ["w7_2", "w7_1"]
    assert store.get_progress("u1", "w7_2")["mastered_at"] == "then" and bank.skill("w7_2")["name"] == "מיומנות 2"
    assert store.review_of("u1")[0]["skill_id"] == "w7_2"
