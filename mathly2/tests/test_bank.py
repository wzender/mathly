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
