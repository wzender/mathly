"""Lesson quizzes through the API (add-lesson-quizzes 2.1-2.4). The `world` fixture and helpers come from test_skills_api."""
import json
from datetime import timedelta

from mathly2.tests.test_skills_api import KID, MGR, MON, OTHER, auth, raw, world  # noqa: F401

LESSON = "t"


def lesson_id(bank, size=4):
    from collections import Counter
    counts = Counter(s["unit"] for s in bank.skills if bank.question_keys(s["id"]))
    return next(l for l, c in counts.items() if c == size)


def start(client, lesson, who=KID):
    return client.post(f"/api/lessons/{lesson}/quiz/start", headers=auth(who))


def right_index(bank, skill_id, key, right=True):
    question = bank._questions[skill_id][key]
    picks = [i for i, c in enumerate(question["choices"]) if bool(c.get("correct")) == right]
    if not right:
        picks = [i for i in picks if question["choices"][i].get("mistake")] or picks
    return picks[0]


def skill_of(key):
    return key.split(":")[0]


def answer(client, attempt, bank, key, right=True, who=KID):
    return client.put(f"/api/attempts/{attempt['id']}/answers", json={"key": key, "choice": right_index(bank, skill_of(key), key, right)},
                      headers=auth(who))


def take(client, bank, lesson, rights, who=KID):
    """Start a quiz and answer the first len(rights) questions right or wrong; submit; return the result."""
    attempt = start(client, lesson, who).json()
    for question, right in zip(attempt["questions"], rights):
        assert answer(client, attempt, bank, question["key"], right, who).status_code == 200
    return client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth(who)).json()


# --- 2.1 starting ---

def test_a_new_student_starts_a_quiz_of_fifteen_questions_with_no_time_limit(world):
    client, _, bank = world
    lesson = lesson_id(bank)
    got = start(client, lesson)
    assert got.status_code == 200
    quiz = got.json()
    assert quiz["state"] == "open" and len(quiz["questions"]) == 15 and quiz["answers"] == {}
    assert quiz["due_at"] is None
    assert quiz["lesson"]["id"] == lesson


def test_a_served_quiz_never_carries_a_right_answer_a_mistake_or_a_skill_name(world):
    client, _, bank = world
    lesson = lesson_id(bank)
    blob = json.dumps(start(client, lesson).json(), ensure_ascii=False)
    assert '"correct"' not in blob and '"mistake"' not in blob and '"skill' not in blob
    skills = {s["name"] for s in bank.skills if s["unit"] == lesson}
    assert not any(name in blob for name in skills)


def test_starting_again_resumes_the_same_open_attempt(world):
    client, _, bank = world
    lesson = lesson_id(bank)
    first = start(client, lesson).json()
    answer(client, first, bank, first["questions"][0]["key"])
    again = start(client, lesson).json()
    assert again["id"] == first["id"] and [q["key"] for q in again["questions"]] == [q["key"] for q in first["questions"]]
    assert len(again["answers"]) == 1 and again["due_at"] == first["due_at"]
    facts = client.get(f"/api/lessons/{lesson}/quiz", headers=auth()).json()
    assert facts["open"]["id"] == first["id"] and facts["best"] is None and facts["attempts"] == 0 and facts["size"] == 15 and facts["minutes"] == 45


def test_a_student_in_no_class_is_refused_a_missing_lesson_is_404_and_a_manager_is_refused(world):
    client, store, bank = world
    other_lesson = next(l["id"] for l in bank.lessons if l["id"] != "t")
    assert start(client, other_lesson, "nobody@school.test").status_code == 403                    # in no class: no lessons
    assert client.get(f"/api/lessons/{other_lesson}/quiz", headers=auth("nobody@school.test")).status_code == 403
    assert start(client, "no-such-lesson").status_code == 404
    assert start(client, LESSON, MGR).status_code == 403


# --- 2.2 answering, submitting, time ---

def test_an_answer_is_saved_can_be_changed_and_submitting_grades_it(world):
    client, _, bank = world
    attempt = start(client, lesson_id(bank)).json()
    key = attempt["questions"][0]["key"]
    answer(client, attempt, bank, key, right=False)
    answer(client, attempt, bank, key, right=True)                                         # changed their mind
    assert client.get(f"/api/attempts/{attempt['id']}", headers=auth()).json()["answers"] == {key: right_index(bank, skill_of(key), key)}
    result = client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth()).json()
    assert result["state"] == "submitted" and result["grade"] == 7 and result["right"] == 1 and result["total"] == 15 and result["timed_out"] is False


def test_submitting_twice_returns_the_same_result(world):
    client, _, bank = world
    attempt = start(client, lesson_id(bank)).json()
    answer(client, attempt, bank, attempt["questions"][0]["key"])
    one = client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth()).json()
    two = client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth()).json()
    assert one == two and client.get(f"/api/attempts/{attempt['id']}", headers=auth()).json() == one


def test_an_answer_long_after_starting_is_still_saved(world):
    client, _, bank = world
    attempt = start(client, lesson_id(bank)).json()
    answer(client, attempt, bank, attempt["questions"][0]["key"])
    client.set_time(MON + timedelta(minutes=46))
    assert answer(client, attempt, bank, attempt["questions"][1]["key"]).status_code == 200
    still = client.get(f"/api/attempts/{attempt['id']}", headers=auth()).json()
    assert still["state"] == "open" and len(still["answers"]) == 2


def test_closing_the_app_for_forty_five_minutes_leaves_the_quiz_open_with_the_answers_given(world):
    client, _, bank = world
    attempt = start(client, lesson_id(bank)).json()
    for q in attempt["questions"][:6]:
        answer(client, attempt, bank, q["key"])
    client.set_time(MON + timedelta(minutes=5))                                            # five minutes in, the app is closed
    client.set_time(MON + timedelta(minutes=50))                                           # it is opened again 45 minutes later
    back = client.get(f"/api/attempts/{attempt['id']}", headers=auth()).json()
    assert back["state"] == "open" and len(back["answers"]) == 6
    done = client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth()).json()
    assert done["state"] == "submitted" and done["timed_out"] is False and done["grade"] == 40 and done["right"] == 6


def test_the_deadline_is_the_servers_a_late_device_clock_changes_nothing(world):
    client, _, bank = world
    attempt = start(client, lesson_id(bank)).json()
    # the server's time is what counts: at 44 minutes the attempt is still open, whatever the device says
    client.set_time(MON + timedelta(minutes=44))
    assert client.get(f"/api/attempts/{attempt['id']}", headers=auth()).json()["state"] == "open"
    assert answer(client, attempt, bank, attempt["questions"][0]["key"]).status_code == 200


def test_another_student_gets_404_and_bad_answers_are_422(world):
    client, store, bank = world
    store.add_member(store.classes()[0]["id"], OTHER)
    attempt = start(client, lesson_id(bank)).json()
    key = attempt["questions"][0]["key"]
    for call in (lambda: client.get(f"/api/attempts/{attempt['id']}", headers=auth(OTHER)),
                 lambda: client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth(OTHER)),
                 lambda: client.put(f"/api/attempts/{attempt['id']}/answers", json={"key": key, "choice": 0}, headers=auth(OTHER))):
        assert call().status_code == 404
    assert client.put(f"/api/attempts/{attempt['id']}/answers", json={"key": "nope:key", "choice": 0}, headers=auth()).status_code == 422
    assert client.put(f"/api/attempts/{attempt['id']}/answers", json={"key": key, "choice": 99}, headers=auth()).status_code == 422
    assert client.get("/api/attempts/not-an-id", headers=auth()).status_code == 404


# --- 2.3 grades and the path ---

def test_the_best_grade_stays_and_a_better_retake_replaces_it(world):
    client, _, bank = world
    lesson = lesson_id(bank)
    take(client, bank, lesson, [True] * 9 + [False] * 6)                                   # 60
    assert client.get(f"/api/lessons/{lesson}/quiz", headers=auth()).json()["best"] == 60
    take(client, bank, lesson, [True] * 12 + [False] * 3)                                  # 80
    assert client.get(f"/api/lessons/{lesson}/quiz", headers=auth()).json()["best"] == 80
    take(client, bank, lesson, [True] * 10 + [False] * 5)                                  # 67: worse
    facts = client.get(f"/api/lessons/{lesson}/quiz", headers=auth()).json()
    assert facts["best"] == 80 and facts["attempts"] == 3


def test_the_grades_screen_data_lists_only_lessons_with_a_submitted_quiz(world):
    client, _, bank = world
    lesson = lesson_id(bank)
    assert client.get("/api/grades", headers=auth()).json() == {"quizzes": [], "exercise_tests": [], "simulations": [], "assignments": []}
    take(client, bank, lesson, [True] * 10 + [False] * 5)
    other = lesson_id(bank, 3)
    abandoned = start(client, other).json()
    answer(client, abandoned, bank, abandoned["questions"][0]["key"])
    assert [q["lesson"]["id"] for q in client.get("/api/grades", headers=auth()).json()["quizzes"]] == [lesson]   # open: not listed yet
    client.set_time(MON + timedelta(hours=1))                                              # no time limit: still open an hour later
    assert [q["lesson"]["id"] for q in client.get("/api/grades", headers=auth()).json()["quizzes"]] == [lesson]
    client.post(f"/api/attempts/{abandoned['id']}/submit", headers=auth())
    grades = client.get("/api/grades", headers=auth()).json()["quizzes"]
    assert {g["lesson"]["id"]: g["best"] for g in grades} == {lesson: 67, other: 7}
    assert all(g["attempts"] == 1 and g["last"] for g in grades)


def test_the_path_gives_each_lesson_its_quiz_state(world):
    client, _, bank = world
    lesson, other = lesson_id(bank), lesson_id(bank, 3)
    quizzes = lambda: {l["id"]: l["quiz"] for l in client.get("/api/path", headers=auth()).json()["lessons"]}
    assert quizzes()[lesson] == {"best": None, "open": False, "due_at": None}
    take(client, bank, lesson, [True] * 14 + [False])
    start(client, other)
    state = quizzes()
    assert state[lesson]["best"] == 93 and state[lesson]["open"] is False
    assert state[other]["best"] is None and state[other]["open"] is True and state[other]["due_at"]


# --- 2.4 written quizzes are not lesson quizzes ---

def test_a_lesson_with_an_authored_written_quiz_still_gets_the_multiple_choice_quiz(world):
    client, _, bank = world
    lesson = next(u["id"] for u in bank.data["units"] if u.get("quiz") and u["id"] == lesson_id(bank))
    assert bank.data["units"][[u["id"] for u in bank.data["units"]].index(lesson)]["quiz"]["questions"]
    quiz = start(client, lesson).json()
    assert len(quiz["questions"]) == 15 and all(len(q["choices"]) >= 2 for q in quiz["questions"])
    keys = {k for s in bank.skills if s["unit"] == lesson for k in bank.question_keys(s["id"])}
    assert {q["key"] for q in quiz["questions"]} <= keys                                   # only bank questions of the lesson's skills


def test_the_draw_never_reads_the_units_written_quiz():
    import inspect
    from mathly2 import quiz as quiz_module
    assert '"quiz"' not in inspect.getsource(quiz_module.draw) and "['quiz']" not in inspect.getsource(quiz_module.draw)


def test_a_retake_has_new_questions_through_the_api(world):
    client, _, bank = world
    lesson = lesson_id(bank)
    first = start(client, lesson).json()
    first_keys = {q["key"] for q in first["questions"]}
    client.post(f"/api/attempts/{first['id']}/submit", headers=auth())
    second = start(client, lesson).json()
    assert second["id"] != first["id"] and len(second["questions"]) == 15
    assert not first_keys & {q["key"] for q in second["questions"]}                        # none of the first attempt's questions


# --- passing: 13 of 15, and the lesson is completed ---

def test_thirteen_of_fifteen_passes_twelve_does_not_and_a_pass_stays(world):
    client, _, bank = world
    lesson = lesson_id(bank)
    lesson_row = lambda: next(l for l in client.get("/api/path", headers=auth()).json()["lessons"] if l["id"] == lesson)
    take(client, bank, lesson, [True] * 12 + [False] * 3)                                  # 80
    assert lesson_row()["passed"] is False and lesson_row()["completed"] is False
    take(client, bank, lesson, [True] * 13 + [False] * 2)                                  # 87
    assert lesson_row()["passed"] is True and lesson_row()["completed"] is True
    take(client, bank, lesson, [True] * 6 + [False] * 9)                                   # 40: worse
    assert lesson_row()["passed"] is True and lesson_row()["completed"] is True
    assert all(s["state"] == "not_started" for s in lesson_row()["skills"])                # the skills themselves are untouched
