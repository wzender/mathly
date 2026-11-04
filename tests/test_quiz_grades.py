"""How a unit-quiz sitting is graded on the server: points x the check's score, 0 for a missing photo, open while a
photographed answer has no scored check."""
from app.quiz_grades import question_result, sitting_view


def attempt(score=None, state="completed", verdict="correct", photo=True):
    return {"attempt_id": "a", "has_photo": photo, "grade_state": state, "score": score, "verdict": verdict}


def sitting(*attempts, unit="t"):
    return {"id": "s1", "unit_id": unit, "submitted_at": "2026-11-04T10:00:00Z", "time_up": False,
            "attempts": list(attempts)}


def test_all_answers_checked_give_the_weighted_sum():
    view = sitting_view(sitting(attempt(100), attempt(60, verdict="partial"), attempt(100), attempt(40, verdict="partial")))
    assert [q["earned"] for q in view["questions"]] == [25, 15, 25, 10]   # the quiz is four questions of 25
    assert view["grade"] == 75 and view["open"] == 0


def test_a_missing_photo_earns_zero_and_does_not_keep_the_grade_open():
    view = sitting_view(sitting(attempt(100), attempt(photo=False, state=None, verdict=None), attempt(100),
                                attempt(photo=False, state=None, verdict=None)))
    assert [q["state"] for q in view["questions"]] == ["checked", "missing", "checked", "missing"]
    assert view["grade"] == 50 and view["open"] == 0


def test_a_photographed_answer_without_a_finished_check_leaves_the_grade_open():
    for waiting in (attempt(state=None, verdict=None), attempt(state="grading", verdict=None),
                    attempt(state="failed", verdict=None)):
        view = sitting_view(sitting(attempt(100), waiting, attempt(100), attempt(100)))
        assert view["grade"] is None and view["open"] == 1
        assert view["questions"][1] == {"points": 25, "earned": None, "state": "waiting"}


def test_an_unreadable_or_needs_review_check_has_no_score_and_stays_open():
    for verdict in ("unreadable", "needs_review"):
        view = sitting_view(sitting(attempt(100), attempt(None, verdict=verdict), attempt(100), attempt(100)))
        assert view["grade"] is None and view["open"] == 1 and view["questions"][1]["state"] == verdict


def test_points_are_rounded_per_question():
    assert question_result(25, attempt(70))["earned"] == 18   # 17.5 rounds up, as the page always did
    assert question_result(25, attempt(0, verdict="incorrect"))["earned"] == 0


def test_a_sitting_of_a_unit_without_a_quiz_has_no_view():
    assert sitting_view(sitting(attempt(100), unit="nope")) is None


def test_the_teachers_score_counts_instead_of_the_automatic_one():
    ai_40_teacher_80 = {**attempt(40, verdict="partial"), "teacher_score": 80}
    view = sitting_view(sitting(attempt(100), ai_40_teacher_80, attempt(100), attempt(100)))
    assert view["questions"][1]["earned"] == 20 and view["questions"][1]["state"] == "teacher"
    assert view["grade"] == 25 + 20 + 25 + 25


def test_a_teacher_score_grades_what_the_check_could_not_or_has_not_yet():
    for unreadable in ({**attempt(None, verdict="unreadable"), "teacher_score": 70},
                       {**attempt(None, state="grading", verdict=None), "teacher_score": 70},
                       {**attempt(None, state=None, verdict=None), "teacher_score": 70}):
        view = sitting_view(sitting(attempt(100), unreadable, attempt(100), attempt(100)))
        assert view["open"] == 0 and view["questions"][1]["earned"] == 18 and view["grade"] == 25 + 18 + 25 + 25


def test_a_teacher_score_of_zero_is_a_score_and_a_comment_alone_changes_nothing():
    zero = {**attempt(100), "teacher_score": 0}
    assert question_result(25, zero)["earned"] == 0
    assert question_result(25, {**attempt(100), "teacher_score": None})["earned"] == 25   # the latest review had no score


def test_a_missing_photo_stays_zero_whatever_the_teacher_says():
    assert question_result(25, {**attempt(photo=False, state=None, verdict=None), "teacher_score": 100}) == \
        {"points": 25, "earned": 0, "state": "missing"}
