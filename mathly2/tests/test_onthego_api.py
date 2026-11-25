"""Practice on the go (onthego.py): a round of questions that need no board, on the lesson round's machinery."""
import json
import random
from collections import Counter

from mathly2 import onthego
from mathly2.tests.test_rounds_api import play
from mathly2.tests.test_skills_api import KID_ID, auth, raw, world  # noqa: F401  (fixtures)


def start(client):
    response = client.post("/api/onthego/start", headers=auth())
    assert response.status_code == 200, response.text
    return response.json()


def test_the_list_is_questions_of_the_bank_and_most_lessons_have_some():
    from mathly2.bank import load_bank
    bank, keys = load_bank(), onthego.load_keys()
    every = {k for s in bank.skills for k in bank.question_keys(s["id"])}
    assert keys and keys <= every and len(keys) < len(every)                  # some questions need a board
    lessons = Counter(next(s["unit"] for s in bank.skills if k.startswith(s["id"] + ":")) for k in keys)
    assert sum(1 for l in bank.lessons if lessons[l["id"]] >= 5) >= len(bank.lessons) - 2


def test_a_round_draws_only_board_free_questions_two_a_skill_at_most_and_carries_no_answer(world):
    client, store, bank = world
    rnd = start(client)
    assert rnd["kind"] == "onthego_round" and rnd["lesson"]["name"] == "תרגול מהיר" and rnd["total"] == onthego.ROUND_SIZE
    rows = store.get_attempt(rnd["id"])["questions"]
    keys = client.app.state.onthego
    assert all(q["key"] in keys for q in rows) and max(Counter(q["skill_id"] for q in rows).values()) <= onthego.PER_SKILL
    assert '"correct"' not in json.dumps(rnd)
    assert start(client)["id"] == rnd["id"]                                   # an open one resumes


def test_answers_count_as_practice_and_the_result_has_no_stars(world):
    client, store, bank = world
    rnd = start(client)
    last = play(client, bank, rnd, [True] * 7 + [False] * 3)["round"]
    assert last["state"] == "done" and last["result"]["right"] == 7 and last["result"]["stars"] is None and len(last["result"]["missed"]) == 3
    assert len(store.recent_answers(KID_ID)) == 10                            # each one a practice answer
    assert start(client)["id"] != rnd["id"]                                   # finished: a new round, other questions first
    used = Counter(q["key"] for r in store.attempts_of(KID_ID, onthego.KIND, "math") for q in r["questions"])
    assert max(used.values()) <= 2


def test_home_says_how_many_and_without_any_the_round_is_refused(world):
    client, store, bank = world
    assert client.get("/api/home", headers=auth()).json()["onthego"] >= 10
    client.app.state.onthego = frozenset()
    assert client.get("/api/home", headers=auth()).json()["onthego"] == 0
    assert client.post("/api/onthego/start", headers=auth()).status_code == 409


def test_the_draw_puts_unmastered_skills_and_the_tests_lessons_first():
    from mathly2.bank import load_bank
    bank, keys = load_bank(), onthego.load_keys()
    lessons = [l["id"] for l in bank.lessons][:4]
    states = {s["id"]: "mastered" for s in bank.skills if s["unit"] == lessons[0]}
    drawn = onthego.draw(bank, keys, lessons, states, {lessons[3]}, {}, random.Random(1))
    units = {next(s["unit"] for s in bank.skills if s["id"] == q["skill_id"]) for q in drawn}
    assert lessons[0] not in units or len(units) == 1 and lessons[3] in units
