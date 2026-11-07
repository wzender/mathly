from mathly2.bank import load_bank
from mathly2.scripts.content_gaps import find_gaps


def test_real_bank_gaps():
    gaps = find_gaps(load_bank().data)
    assert len(gaps["skills without a worked example"]) == 96
    assert len(gaps["skills without faded examples"]) == 96
    assert len(gaps["lessons without a quiz"]) == 20
    assert len(gaps["skills without questions"]) == 1
    assert len(gaps["mistakes without a skill to go back to"]) == 204


def test_a_skill_with_an_example_and_all_steps_explained_is_not_listed():
    data = {"units": [{"id": "u", "quiz": {"questions": []}}],
            "skills": [{"id": "s", "unit": "u", "questions": [{}] * 10,
                        "worked_example": {"steps": [{"why": ["a", "b"]}]}, "faded_examples": [{}]}],
            "mistakes": {}}
    assert all(not items for items in find_gaps(data).values())


def test_step_without_why_is_listed():
    data = {"units": [], "skills": [{"id": "s", "unit": "u", "worked_example": {"steps": [{"why": ["a"]}, {}]}}],
            "mistakes": {}}
    assert find_gaps(data)["worked-example steps without 'why this step?' choices"] == ["s step 2"]
