"""Lesson rounds and the lesson's stars (game-home-lesson-rounds 1.2, 1.3)."""
from collections import Counter

from mathly2.tests.test_skills_api import KID_ID, MON, TUE, auth, raw, right_choice, world, wrong_choice  # noqa: F401

STAMP = "2026-10-05T10:00:00+00:00"


def skills_of(bank, lesson):
    return [s["id"] for s in bank.skills if s["unit"] == lesson and bank.question_keys(s["id"])]


def a_lesson(bank, n=5):
    return next(l["id"] for l in bank.lessons if len(skills_of(bank, l["id"])) == n)


def start(client, lesson):
    response = client.post(f"/api/lessons/{lesson}/round/start", headers=auth())
    assert response.status_code == 200, response.text
    return response.json()


def play(client, bank, rnd, rights):
    """Answer the round's questions in order, right or wrong; return the last answer's response."""
    got = None
    for right in rights:
        q = rnd["question"]
        skill = next(s["id"] for s in bank.skills if q["key"] in bank.question_keys(s["id"]))
        choice = (right_choice if right else wrong_choice)(bank, skill, q["key"])
        response = client.post(f"/api/rounds/{rnd['id']}/answer", headers=auth(), json={"key": q["key"], "choice": choice})
        assert response.status_code == 200, response.text
        got = response.json()
        rnd = got["round"]
    return got


def map_row(client, lesson):
    home = client.get("/api/home", headers=auth()).json()["map"]
    return home, next(r for r in home["lessons"] if r["id"] == lesson)


def test_a_round_of_five_fresh_skills_is_ten_questions_two_each_and_never_carries_the_answer(world):
    client, _, bank = world
    lesson = a_lesson(bank)
    rnd = start(client, lesson)
    assert rnd["state"] == "open" and rnd["total"] == 10 and rnd["results"] == []
    assert '"correct"' not in str(rnd["question"]).replace("'", '"')
    row = client.app.state.store.get_attempt(rnd["id"])
    assert sorted(Counter(q["skill_id"] for q in row["questions"]).values()) == [2] * 5
    assert start(client, lesson)["id"] == rnd["id"]                                         # an open round resumes


def test_a_round_leaves_out_mastered_skills_at_most_three_from_each(world):
    client, store, bank = world
    lesson = a_lesson(bank)
    skills = skills_of(bank, lesson)
    for s in skills[:4]:
        store.save_progress(KID_ID, s, started_at=STAMP, mastered_at=STAMP)
    rnd = start(client, lesson)
    assert rnd["total"] == 3 and {q["skill_id"] for q in store.get_attempt(rnd["id"])["questions"]} == {skills[4]}


def test_answers_must_come_in_order_and_each_is_a_practice_answer(world):
    client, store, bank = world
    rnd = start(client, a_lesson(bank))
    wrong_key = store.get_attempt(rnd["id"])["questions"][1]["key"]
    assert client.post(f"/api/rounds/{rnd['id']}/answer", headers=auth(), json={"key": wrong_key, "choice": 0}).status_code == 409
    got = play(client, bank, rnd, [False])
    assert got["correct"] is False and got["mistake"] is not None and got["round"]["results"] == [False]
    skill = store.get_attempt(rnd["id"])["questions"][0]["skill_id"]
    assert store.get_progress(KID_ID, skill)["started_at"]                                   # the skill is in learning now
    assert any(r["question_key"] == rnd["question"]["key"] for r in store.review_of(KID_ID)) if hasattr(store, "review_of") else True


def test_the_result_after_the_last_answer_and_the_stars(world):
    client, _, bank = world
    lesson = a_lesson(bank)
    _, row = map_row(client, lesson)
    assert row["stars"] == 0
    got = play(client, bank, start(client, lesson), [True] * 7 + [False] * 3)
    result = got["round"]["result"]
    assert got["round"]["state"] == "done" and result["right"] == 7 and result["total"] == 10 and result["stars"] == 1 and len(result["missed"]) == 3
    assert map_row(client, lesson)[1]["stars"] == 1
    play(client, bank, start(client, lesson), [True] * 8 + [False] * 2)
    assert map_row(client, lesson)[1]["stars"] == 2
    play(client, bank, start(client, lesson), [False] * 10)
    assert map_row(client, lesson)[1]["stars"] == 2                                        # stars never go down


def test_two_good_rounds_on_two_days_master_the_lesson_three_stars(world):
    client, _, bank = world
    lesson = a_lesson(bank)
    client.set_time(MON)
    first = play(client, bank, start(client, lesson), [True] * 10)["round"]["result"]
    assert first["stars"] == 2 and len(first["almost"]) == 5 and first["mastered"] == []
    client.set_time(TUE)
    last = play(client, bank, start(client, lesson), [True] * 10)
    assert last["round"]["result"]["stars"] == 3 and len(last["round"]["result"]["mastered"]) == 5
    home, row = map_row(client, lesson)
    assert row["stars"] == 3 and home["perfect"] == 1


def test_the_map_names_the_next_lesson_open_round_first(world):
    client, _, bank = world
    home = client.get("/api/home", headers=auth()).json()["map"]
    playable = home["lessons"]
    assert home["next"] == playable[0]["id"] and home["max_stars"] == 3 * len(playable) and home["stars"] == 0
    later = playable[3]["id"]
    start(client, later)
    home, row = map_row(client, later)
    assert home["next"] == later and row["round_open"] is True
