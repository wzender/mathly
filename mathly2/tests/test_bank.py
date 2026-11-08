import copy
import json

import pytest

from mathly2.bank import BANK_PATH, BankError, check_bank, load_bank


@pytest.fixture(scope="module")
def raw():
    return json.loads(BANK_PATH.read_text(encoding="utf-8"))


def test_real_bank_is_sound_and_has_the_expected_size():
    bank = load_bank()
    assert (len(bank.lessons), len(bank.skills), len(bank.mistakes)) == (24, 96, 244)
    assert sum(len(s.get("questions", [])) for s in bank.skills) == 1050


def broken(raw, change):
    data = copy.deepcopy(raw)
    change(data)
    return check_bank(data)


def test_duplicate_skill_id(raw):
    problems = broken(raw, lambda d: d["skills"][1].update(id=d["skills"][0]["id"]))
    assert any("duplicate skill id" in p for p in problems)


def test_question_with_two_correct_choices(raw):
    def change(d):
        d["skills"][0]["questions"][0]["choices"][1]["correct"] = True
    assert any("2 correct choices" in p for p in broken(raw, change))


def test_question_with_no_correct_choice(raw):
    def change(d):
        for c in d["skills"][0]["questions"][0]["choices"]:
            c.pop("correct", None)
    assert any("0 correct choices" in p for p in broken(raw, change))


def test_unknown_mistake_on_a_choice(raw):
    def change(d):
        d["skills"][0]["questions"][0]["choices"][1]["mistake"] = "nope"
    assert any("unknown mistake 'nope'" in p for p in broken(raw, change))


def test_mistake_pointing_back_to_a_missing_skill(raw):
    def change(d):
        d["mistakes"][next(iter(d["mistakes"]))]["back"] = "missing_skill"
    assert any("missing_skill" in p for p in broken(raw, change))


def test_empty_back_is_allowed_but_a_wrong_one_is_not(raw):
    def change(d):
        d["mistakes"][next(iter(d["mistakes"]))]["back"] = ""
    assert broken(raw, change) == []


def test_skill_in_a_missing_lesson(raw):
    assert any("unknown lesson" in p for p in broken(raw, lambda d: d["skills"][0].update(unit="zz")))


def test_missing_section_is_reported(raw):
    assert check_bank({"units": []}) == ["missing 'skills'"]


def test_broken_bank_stops_loading(tmp_path, raw):
    raw = copy.deepcopy(raw)
    raw["skills"][0]["unit"] = "zz"
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(BankError, match="unknown lesson"):
        load_bank(path)


# --- question keys (task 1.1) ---

from mathly2.bank import question_key


def test_real_bank_has_a_distinct_key_for_every_question():
    bank = load_bank()
    keys = [k for s in bank.skills for k in bank.question_keys(s["id"])]
    assert len(keys) == 1050 and len(set(keys)) == 1050


def test_question_key_is_stable_and_changes_with_the_content(raw):
    question = raw["skills"][0]["questions"][0]
    sid = raw["skills"][0]["id"]
    assert question_key(sid, question) == question_key(sid, copy.deepcopy(question))
    edited = copy.deepcopy(question)
    edited["question"] += " "
    assert question_key(sid, edited) != question_key(sid, question)


def test_keys_survive_reordering_questions(raw):
    data = copy.deepcopy(raw)
    before = set(load_bank().question_keys(data["skills"][0]["id"]))
    data["skills"][0]["questions"].reverse()
    assert set(Bank(data).question_keys(data["skills"][0]["id"])) == before


def test_a_duplicated_question_in_a_skill_is_rejected(raw):
    def change(d):
        d["skills"][0]["questions"].append(copy.deepcopy(d["skills"][0]["questions"][0]))
    assert any("identical to an earlier question" in p for p in broken(raw, change))


# --- the solved example for the help button (add-learning-core 1.1) ---

def _good_example():
    return {"question": "$x² + 5x + 6$", "answer": "$(x + 2)(x + 3)$",
            "steps": [{"do": "מוצאים 2 ו־3", "why": "כי המכפלה 6 והסכום 5"}, {"do": "כותבים $(x + 2)(x + 3)$", "why": "כך מפרקים טרינום"}]}


def _with_example(raw, example):
    data = copy.deepcopy(raw)
    data["skills"][0]["worked_example"] = example
    return data


def test_a_valid_solved_example_passes(raw):
    assert check_bank(_with_example(raw, _good_example())) == []


def test_the_real_bank_without_solved_examples_still_loads():
    load_bank()


def test_a_solved_example_needs_a_question_steps_and_an_answer(raw):
    for broken_example in ({**_good_example(), "question": ""}, {**_good_example(), "steps": []}, {**_good_example(), "answer": ""}):
        assert any("needs a question, steps and an answer" in p for p in check_bank(_with_example(raw, broken_example)))


def test_every_step_needs_what_is_done_and_why_as_text(raw):
    example = _good_example()
    example["steps"][0].pop("do")
    assert any("step 1: no 'do'" in p for p in check_bank(_with_example(raw, example)))
    example = _good_example()
    example["steps"][1]["why"] = ""
    assert any("step 2: 'why' must be text" in p for p in check_bank(_with_example(raw, example)))
    example = _good_example()
    example["steps"][0]["why"] = [{"text": "a", "correct": True}, {"text": "b"}]       # the earlier plan's multiple choice
    assert any("step 1: 'why' must be text" in p for p in check_bank(_with_example(raw, example)))


def test_faded_examples_from_the_earlier_plan_are_not_read_or_refused(raw):
    data = _with_example(raw, _good_example())
    data["skills"][0]["faded_examples"] = [{"anything": 1}]
    assert check_bank(data) == []


# --- serving practice questions (task 1.3) ---

from mathly2.bank import Bank


def _skill_with_figure(bank):
    return next(s for s in bank.skills if any("figure" in q for q in s.get("questions", [])))


def test_a_served_question_never_carries_the_answer():
    bank = load_bank()
    for skill in bank.skills:
        for key in bank.question_keys(skill["id"]):
            text = json.dumps(bank.practice_question(skill["id"], key), ensure_ascii=False)
            assert '"correct"' not in text and '"mistake"' not in text


def test_served_choices_keep_their_bank_position():
    bank = load_bank()
    skill = bank.skills[0]
    key = bank.question_keys(skill["id"])[0]
    served = bank.practice_question(skill["id"], key)
    original = skill["questions"][0]["choices"]
    assert [c["index"] for c in served["choices"]] == list(range(len(original)))
    assert [c["text"] for c in served["choices"]] == [c["text"] for c in original]


def test_figures_and_graphs_are_served_with_the_question():
    bank = load_bank()
    skill = _skill_with_figure(bank)
    for key in bank.question_keys(skill["id"]):
        question = next(q for q in skill["questions"] if question_key(skill["id"], q) == key)
        served = bank.practice_question(skill["id"], key)
        assert ("figure" in served) == ("figure" in question)


def test_grading_a_right_and_a_wrong_choice():
    bank = load_bank()
    skill = bank.skills[0]
    question = skill["questions"][0]
    key = question_key(skill["id"], question)
    right = next(i for i, c in enumerate(question["choices"]) if c.get("correct"))
    wrong = next(i for i, c in enumerate(question["choices"]) if c.get("mistake"))
    assert bank.grade(skill["id"], key, right) == {"correct": True, "mistake": None}
    result = bank.grade(skill["id"], key, wrong)
    assert result["correct"] is False
    mistake = result["mistake"]
    assert mistake["id"] == question["choices"][wrong]["mistake"]
    assert mistake["name"] and mistake["tip"]
    assert set(result) == {"correct", "mistake"}            # no index or text of the right choice
    assert set(mistake) == {"id", "name", "tip", "back"}


def test_grading_an_unknown_question_or_choice_gives_none():
    bank = load_bank()
    sid = bank.skills[0]["id"]
    key = bank.question_keys(sid)[0]
    assert bank.grade(sid, "nope", 0) is None
    assert bank.grade(sid, key, 99) is None
    assert bank.grade(sid, key, -1) is None
    assert bank.grade(sid, key, "0") is None


def test_mistake_back_is_none_when_the_bank_has_none():
    bank = load_bank()
    without = next(m for m, v in bank.mistakes.items() if not v.get("back"))
    with_back = next(m for m, v in bank.mistakes.items() if v.get("back"))
    assert bank.mistake(without)["back"] is None
    assert bank.mistake(with_back)["back"] == bank.mistakes[with_back]["back"]
    assert bank.mistake(None) is None
