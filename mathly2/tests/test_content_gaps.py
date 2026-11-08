from mathly2.bank import load_bank
from mathly2.scripts import content_gaps
from mathly2.scripts.content_gaps import find_gaps


def test_real_bank_gaps():
    gaps = find_gaps(load_bank().data)
    assert len(gaps["skills without a solved example"]) == 96
    assert gaps["skills without questions"] == ["a_30_side"]
    assert len(gaps["mistakes without a skill to go back to"]) == 204
    assert gaps["skills with fewer than 10 questions"] == []
    assert set(gaps) == {"skills without a solved example", "skills without questions", "skills with fewer than 10 questions",
                         "mistakes without a skill to go back to"}


def test_a_complete_skill_is_not_listed():
    data = {"units": [], "skills": [{"id": "s", "unit": "u", "questions": [{}] * 10, "worked_example": {"steps": []}}],
            "mistakes": {"m": {"back": "s"}}}
    assert all(not items for items in find_gaps(data).values())


def test_few_questions_are_listed_with_their_count_and_the_threshold_can_change():
    data = {"units": [], "skills": [{"id": "a", "unit": "u", "questions": [{}] * 3, "worked_example": {}},
                                    {"id": "b", "unit": "u", "questions": [{}] * 9, "worked_example": {}}], "mistakes": {}}
    assert find_gaps(data)["skills with fewer than 10 questions"] == ["a (3)", "b (9)"]
    assert find_gaps(data, min_questions=5)["skills with fewer than 5 questions"] == ["a (3)"]


def test_a_mistake_with_an_empty_back_is_a_gap():
    data = {"units": [], "skills": [], "mistakes": {"x": {"back": ""}, "y": {}, "z": {"back": "s"}}}
    assert find_gaps(data)["mistakes without a skill to go back to"] == ["x", "y"]


def test_the_command_prints_each_gap_with_its_count(capsys):
    assert content_gaps.main([]) == 0
    out = capsys.readouterr().out
    assert "skills without a solved example: 96" in out and "skills without questions: 1" in out and "a_30_side" in out
