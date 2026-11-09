"""The review tab (add-review-tab 2.1-2.3): wrong answers collect in חזרה, are redone there, and it is practice only."""
import copy
from datetime import timedelta

from mathly2 import attempts, clock
from mathly2.tests.test_quizzes_api import answer, lesson_id, right_index, skill_of, start, take
from mathly2.tests.test_skills_api import KID, KID_ID, MON, OTHER, TEACHER, auth, raw, world  # noqa: F401


def review(client, who=KID, after=None):
    return client.get("/api/review" + (f"?after={after}" if after else ""), headers=auth(who)).json()


def redo(client, key, bank, right, who=KID):
    return client.post("/api/review/answer", json={"key": key, "choice": right_index(bank, skill_of(key), key, right)}, headers=auth(who))


def practice(client, skill_id, bank, right):
    q = client.get(f"/api/skills/{skill_id}", headers=auth()).json()["question"]
    got = client.post(f"/api/skills/{skill_id}/answer", json={"question_key": q["key"], "choice": right_index(bank, skill_id, q["key"], right)}, headers=auth())
    assert got.status_code == 200 and got.json()["correct"] is right
    return q["key"]


def test_a_wrong_practice_answer_goes_to_review_and_a_right_one_does_not(world):
    client, store, bank = world
    skill = client.ids[0]
    right_key = practice(client, skill, bank, True)
    assert review(client) == {"count": 0, "question": None}
    wrong_key = practice(client, skill, bank, False)
    got = review(client)
    assert got["count"] == 1 and got["question"]["key"] == wrong_key and got["question"]["skill"]["id"] == skill and got["question"]["source"] == "practice"
    assert right_key != wrong_key


def test_a_quiz_sends_its_wrong_and_unanswered_questions(world):
    client, store, bank = world
    lesson = lesson_id(bank)
    result = take(client, bank, lesson, [True] * 12 + [False] * 2)                     # 12 right, 2 wrong, the 15th never answered
    assert result["right"] == 12
    rows = store.review_of(KID_ID)
    assert len(rows) == 3 and {r["source"] for r in rows} == {"quiz"}
    again = client.post(f"/api/attempts/{start(client, lesson).json()['id']}/submit", headers=auth()).json()      # a second, empty quiz
    assert len(store.review_of(KID_ID)) >= 3 and again["right"] == 0
    submitted_twice = store.review_of(KID_ID)
    attempt = store.attempts_of(KID_ID, "quiz")[0]
    attempts.submit(store, bank, store.get_attempt(attempt["id"]), clock.now())                  # a repeated submit adds nothing
    assert store.review_of(KID_ID) == submitted_twice


def test_a_timed_out_quiz_sends_its_unanswered_questions(world):
    client, store, bank = world
    lesson = lesson_id(bank)
    attempt = start(client, lesson).json()
    answer(client, attempt, bank, attempt["questions"][0]["key"], True)
    client.set_time(MON + timedelta(minutes=46))
    client.get(f"/api/attempts/{attempt['id']}", headers=auth())                              # the read settles it
    assert len(store.review_of(KID_ID)) == 14                                                  # the right one is not there, the 14 unanswered are


def test_tests_and_the_simulation_send_their_wrong_answers_too(world):
    client, store, bank = world
    skill = client.ids[0]
    keys = bank.question_keys(skill)[:3]
    for kind, scope in (("exercise_test", "1:1"), ("simulation", "1")):
        row = store.create_attempt(KID_ID, kind, scope, MON, MON + timedelta(minutes=45), [{"skill_id": skill, "key": k} for k in keys])
        store.save_attempt(row["id"], answers={keys[0]: right_index(bank, skill, keys[0], True), keys[1]: right_index(bank, skill, keys[1], False)})
        attempts.submit(store, bank, store.get_attempt(row["id"]), MON + timedelta(minutes=10))
    rows = {r["question_key"]: r["source"] for r in store.review_of(KID_ID)}
    assert set(rows) == {keys[1], keys[2]} and rows[keys[1]] == "exercise_test"                  # the first source stays; a question is there once


def test_a_question_is_in_the_list_once(world):
    _, store, _ = world
    assert store.add_review(KID_ID, [("s", "s:k", "practice")]) == 1 and store.add_review(KID_ID, [("s", "s:k", "quiz")]) == 0
    assert [r["source"] for r in store.review_of(KID_ID)] == ["practice"]


def test_redoing_wrong_keeps_it_names_the_mistake_and_never_shows_the_right_choice(world):
    client, store, bank = world
    skill = client.ids[0]
    key = practice(client, skill, bank, False)
    served = review(client)["question"]
    assert not any(k in str(served) for k in ("correct", "mistake")) and set(served["choices"][0]) == {"index", "text"}     # nothing reveals the answer
    got = redo(client, key, bank, False)
    assert got.status_code == 200
    body = got.json()
    assert body["correct"] is False and body["count"] == 1 and body["mistake"] and body["mistake"]["name"] and body["mistake"]["tip"]
    assert "right" not in str(body).lower() and "correct_index" not in body and body["next"]["key"] == key                # alone in the list: it comes again
    assert [r["question_key"] for r in store.review_of(KID_ID)] == [key]


def test_redoing_right_removes_it_and_goes_to_the_next_oldest_never_the_one_just_answered(world):
    client, store, bank = world
    first, second, third = (store.add_review(KID_ID, [(client.ids[0], k, "practice")], MON + timedelta(minutes=i)) and k for i, k in enumerate(bank.question_keys(client.ids[0])[:3]))
    assert review(client)["question"]["key"] == first and review(client, after=first)["question"]["key"] == second
    got = redo(client, first, bank, True).json()
    assert got["correct"] is True and got["mistake"] is None and got["count"] == 2 and got["next"]["key"] == second
    wrong = redo(client, second, bank, False).json()
    assert wrong["count"] == 2 and wrong["next"]["key"] == third                                  # others wait: not the one just answered
    assert [r["question_key"] for r in store.review_of(KID_ID)] == [second, third]


def test_redo_refuses_a_question_not_in_the_list_and_a_bad_choice(world):
    client, store, bank = world
    skill = client.ids[0]
    key = bank.question_keys(skill)[0]
    assert redo(client, key, bank, True).status_code == 409
    store.add_review(KID_ID, [(skill, key, "practice")])
    assert client.post("/api/review/answer", json={"key": key, "choice": 99}, headers=auth()).status_code == 422
    assert redo(client, key, bank, True, OTHER).status_code in (403, 409)                         # another student has nothing to redo


def test_it_is_practice_only_mastery_and_rounds_are_untouched_and_the_daily_goal_counts_it(world):
    client, store, bank = world
    skill = client.ids[0]
    keys = bank.question_keys(skill)[:6]
    store.add_review(KID_ID, [(skill, k, "practice") for k in keys])
    path = lambda: client.get("/api/path", headers=auth()).json()
    before_answers, before_done = len(store.answers_of(KID_ID, skill)), path()["today"]["done"]
    round_before = client.get(f"/api/skills/{skill}", headers=auth()).json()["round"]
    for k in keys:
        assert redo(client, k, bank, True).json()["correct"] is True
    assert store.review_of(KID_ID) == [] and len(store.answers_of(KID_ID, skill)) == before_answers            # no practice answer was written
    assert store.get_progress(KID_ID, skill) is None or not store.get_progress(KID_ID, skill).get("mastered_at")
    state = next(s["state"] for l in path()["lessons"] for s in l["skills"] if s["id"] == skill)
    assert state == "not_started"
    assert path()["today"]["done"] == before_done + 6                                               # each right answer counts toward the goal
    assert client.get(f"/api/skills/{skill}", headers=auth()).json()["round"] == round_before                  # a practice round is unchanged


def test_an_empty_list_and_each_students_own_list(world):
    client, store, bank = world
    store.add_review(KID_ID, [(client.ids[0], bank.question_keys(client.ids[0])[0], "practice")])
    assert review(client)["count"] == 1
    assert review(client, TEACHER) == {"count": 0, "question": None}
    assert client.get("/api/review", headers={}).status_code in (401, 403)
