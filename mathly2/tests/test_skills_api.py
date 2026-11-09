import copy
import json
import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from mathly2 import clock
from mathly2.bank import Bank, load_bank, question_key
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

TEACHER, KID, OTHER, MGR = "t@school.test", "kid@school.test", "other@school.test", "mgr@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))      # the id the dev sign-in gives this email
MON = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
TUE = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
SOLVED = {"question": "$x² + 5x + 6$", "answer": "$(x + 2)(x + 3)$",
          "steps": [{"do": "מוצאים 2 ו־3", "why": "המכפלה 6 והסכום 5"}, {"do": "כותבים $(x + 2)(x + 3)$", "why": "כך מפרקים"}]}


def auth(email=KID):
    return {"Authorization": f"Bearer dev:{email}"}


@pytest.fixture(scope="module")
def raw():
    return copy.deepcopy(load_bank().data)


@pytest.fixture
def world(raw, monkeypatch):
    """(client, store, bank). client.ids = (a skill with no solved example, a skill that has one). The student is in a class
    that studies every lesson; the server's clock can be set with client.set_time."""
    data = copy.deepcopy(raw)
    with_questions = [s for s in data["skills"] if len(s.get("questions", [])) >= 4]
    bare, solved = with_questions[0]["id"], with_questions[1]["id"]
    for s in data["skills"]:
        if s["id"] == solved:
            s["worked_example"] = copy.deepcopy(SOLVED)
    bank = Bank(data)
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    store.add_member(store.create_class("setup", "A", lessons=[u["id"] for u in data["units"]])["id"], KID)
    client = TestClient(create_app(Settings(teachers=frozenset({TEACHER})), bank=bank, store=store))
    moment = {"now": MON}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    client.ids = (bare, solved)
    client.set_time = lambda value: moment.update(now=value)
    return client, store, bank


def right_choice(bank, skill_id, key):
    question = next(q for q in bank.skill(skill_id)["questions"] if question_key(skill_id, q) == key)
    return next(i for i, c in enumerate(question["choices"]) if c.get("correct"))


def wrong_choice(bank, skill_id, key):
    question = next(q for q in bank.skill(skill_id)["questions"] if question_key(skill_id, q) == key)
    return next(i for i, c in enumerate(question["choices"]) if not c.get("correct"))


def open_skill(client, skill_id, who=KID):
    response = client.get(f"/api/skills/{skill_id}", headers=auth(who))
    assert response.status_code == 200, response.text
    return response.json()


def respond(client, bank, skill_id, correct=True, who=KID):
    """Answer the question on screen; return the answer response."""
    shown = open_skill(client, skill_id, who)["question"]
    if shown is None:                                          # the round is done: "סבב חדש", as the student would
        assert client.post(f"/api/skills/{skill_id}/round", headers=auth(who)).status_code == 200
        shown = open_skill(client, skill_id, who)["question"]
    pick = (right_choice if correct else wrong_choice)(bank, skill_id, shown["key"])
    response = client.post(f"/api/skills/{skill_id}/answer", json={"question_key": shown["key"], "choice": pick}, headers=auth(who))
    assert response.status_code == 200, response.text
    return response.json()


def master(client, bank, skill_id):
    client.set_time(MON)
    respond(client, bank, skill_id)
    respond(client, bank, skill_id)
    client.set_time(TUE)
    return respond(client, bank, skill_id)


# --- opening a skill (spec: exercise-screen) ---

def test_a_skill_opens_with_its_lesson_state_question_and_counts(world):
    client, _, bank = world
    bare = client.ids[0]
    skill = open_skill(client, bare)
    lesson = next(l for l in bank.lessons if l["id"] == bank.skill(bare)["unit"])
    assert skill["lesson"] == {"id": lesson["id"], "name": lesson["name"]} and skill["name"] == bank.skill(bare)["name"]
    assert skill["state"] == "not_started" and skill["question"]["key"].startswith(bare + ":")
    assert skill["round"]["total"] == len(bank.practice_keys(bare)) and skill["round"]["answered"] == 0 and skill["correct_in_row"] == 0
    assert skill["practice_available"] is True and set(skill) >= {"requires", "opens", "help", "today"}
    assert "stage" not in skill and "faded_examples" not in skill and "worked_example" not in skill


def test_a_practice_question_never_carries_the_answer(world):
    client, _, _ = world
    text = json.dumps(open_skill(client, client.ids[0])["question"], ensure_ascii=False)
    assert '"correct"' not in text and '"mistake"' not in text


def test_help_has_the_explanation_and_a_solved_example_only_when_the_bank_has_one(world):
    client, _, bank = world
    bare, solved = client.ids
    assert open_skill(client, bare)["help"] == {"explanation": bank.skill(bare)["description"], "solved_example": None}
    assert open_skill(client, solved)["help"]["solved_example"] == SOLVED


def test_requires_and_opens_list_the_neighbouring_skills_by_name(world):
    client, _, bank = world
    skill = next(s for s in bank.skills if s.get("prereqs") and s.get("questions"))
    needed = bank.skill(skill["prereqs"][0])
    opened = open_skill(client, skill["id"])
    assert {"id": needed["id"], "name": needed["name"]} in opened["requires"]
    assert {"id": skill["id"], "name": skill["name"]} in open_skill(client, needed["id"])["opens"]


def test_a_skill_without_questions_has_no_question_and_cannot_be_answered(world):
    client, _, _ = world
    empty = open_skill(client, "a_30_side")
    assert empty["question"] is None and empty["practice_available"] is False and empty["round"]["total"] == 0
    assert client.post("/api/skills/a_30_side/answer", json={"question_key": "x", "choice": 0}, headers=auth()).status_code == 409


def test_unknown_skill_and_the_removed_stage_route(world):
    client, _, _ = world
    assert client.get("/api/skills/nope", headers=auth()).status_code == 404
    assert client.post(f"/api/skills/{client.ids[0]}/stage", json={"event": "started"}, headers=auth()).status_code in (404, 405)


def test_a_student_in_no_class_is_refused_everywhere(world):
    client, _, _ = world
    skill, stranger = client.ids[0], auth("stranger@school.test")
    assert client.get(f"/api/skills/{skill}", headers=stranger).status_code == 403
    assert client.get("/api/path", headers=stranger).status_code == 403
    assert client.get("/api/collection", headers=stranger).status_code == 403
    assert client.post(f"/api/skills/{skill}/help", headers=stranger).status_code == 403
    assert client.post(f"/api/skills/{skill}/answer", json={"question_key": "k", "choice": 0}, headers=stranger).status_code == 403


# --- answers (spec: exercise-screen, skill-mastery) ---

def test_a_right_answer_returns_a_different_next_question_and_counts_as_solved(world):
    client, _, bank = world
    bare = client.ids[0]
    first = open_skill(client, bare)["question"]["key"]
    result = respond(client, bank, bare)
    assert result["correct"] is True and result["mistake"] is None and result["state"] == "learning"
    assert result["next_question"]["key"] != first and result["round"]["answered"] == 1 and result["round"]["results"] == [True] and result["round"]["total"] == len(bank.practice_keys(bare))
    assert open_skill(client, bare)["question"]["key"] == result["next_question"]["key"]


def test_a_wrong_answer_names_the_mistake_hides_the_right_choice_and_is_not_solved(world):
    client, _, bank = world
    bare = client.ids[0]
    shown = open_skill(client, bare)["question"]
    question = next(q for q in bank.skill(bare)["questions"] if question_key(bare, q) == shown["key"])
    index = next(i for i, c in enumerate(question["choices"]) if c.get("mistake"))
    result = client.post(f"/api/skills/{bare}/answer", json={"question_key": shown["key"], "choice": index}, headers=auth()).json()
    assert result["correct"] is False and result["mistake"]["id"] == question["choices"][index]["mistake"]
    assert result["mistake"]["name"] and result["mistake"]["tip"] and set(result["mistake"]) <= {"id", "name", "tip", "back", "back_name"}
    assert result["next_question"]["key"] != shown["key"] and result["round"]["results"] == [False]
    assert '"correct": true' not in json.dumps(result)


def test_a_mistake_with_a_skill_to_go_back_to_names_it(world):
    client, store, bank = world
    skill_id, question, index = next((s["id"], q, i) for s in bank.skills for q in s.get("questions", [])
                                     for i, c in enumerate(q["choices"]) if c.get("mistake") and bank.mistakes[c["mistake"]].get("back"))
    key = question_key(skill_id, question)
    store.save_progress(KID_ID, skill_id, current_key=key)
    result = client.post(f"/api/skills/{skill_id}/answer", json={"question_key": key, "choice": index}, headers=auth()).json()
    back = bank.mistakes[question["choices"][index]["mistake"]]["back"]
    assert result["mistake"]["back"] == back and result["mistake"]["back_name"] == bank.skill(back)["name"]


def test_the_server_dates_the_answer_not_the_device(world):
    client, store, bank = world
    bare = client.ids[0]
    shown = open_skill(client, bare)["question"]
    client.post(f"/api/skills/{bare}/answer", json={"question_key": shown["key"], "choice": right_choice(bank, bare, shown["key"]),
                                                    "day": "2030-01-01"}, headers={**auth(), "Date": "Tue, 01 Jan 2030 00:00:00 GMT"})
    assert store.last_counted_answers(KID_ID, bare, 1)[0]["day"] == date(2026, 11, 2)


def test_an_answer_for_a_question_not_on_screen_or_replayed_is_refused(world):
    client, store, bank = world
    bare = client.ids[0]
    shown = open_skill(client, bare)["question"]
    other = next(k for k in bank.question_keys(bare) if k != shown["key"])
    assert client.post(f"/api/skills/{bare}/answer", json={"question_key": other, "choice": 0}, headers=auth()).status_code == 409
    body = {"question_key": shown["key"], "choice": right_choice(bank, bare, shown["key"])}
    assert client.post(f"/api/skills/{bare}/answer", json=body, headers=auth()).status_code == 200
    assert client.post(f"/api/skills/{bare}/answer", json=body, headers=auth()).status_code == 409
    assert len(store.last_counted_answers(KID_ID, bare, 5)) == 1


def test_bad_choices_are_refused(world):
    client, _, _ = world
    bare = client.ids[0]
    shown = open_skill(client, bare)["question"]
    for choice in (99, -1):
        assert client.post(f"/api/skills/{bare}/answer", json={"question_key": shown["key"], "choice": choice}, headers=auth()).status_code == 422


def test_mastered_over_two_days_through_the_api(world):
    client, _, bank = world
    bare = client.ids[0]
    assert respond(client, bank, bare)["state"] == "learning"
    assert respond(client, bank, bare)["state"] == "learning"
    client.set_time(TUE)
    last = respond(client, bank, bare)
    assert last["state"] == "mastered" and last["mastered_now"] is True and last["correct_in_row"] == 3
    again = respond(client, bank, bare, correct=False)
    assert again["state"] == "mastered" and again["mastered_now"] is False


def test_three_in_a_row_on_one_day_is_not_mastered(world):
    client, _, bank = world
    assert [respond(client, bank, client.ids[0])["state"] for _ in range(3)] == ["learning"] * 3


def test_an_answer_after_help_is_not_counted_and_does_not_break_the_run(world):
    client, store, bank = world
    bare = client.ids[0]
    respond(client, bank, bare)
    respond(client, bank, bare)
    assert client.post(f"/api/skills/{bare}/help", headers=auth()).status_code == 200
    helped = respond(client, bank, bare)
    assert helped["correct"] and helped["state"] == "learning"
    assert len(store.last_counted_answers(KID_ID, bare, 10)) == 2           # the helped one is stored, not counted
    assert store.get_progress(KID_ID, bare)["current_helped"] is False      # help applies to one question only
    client.set_time(TUE)
    assert respond(client, bank, bare)["state"] == "mastered"                # Mon, Mon, (help), Tue


def test_help_for_an_unknown_skill_is_404(world):
    assert world[0].post("/api/skills/nope/help", headers=auth()).status_code == 404


# --- the path (spec: learning-path) ---

def test_the_path_shows_every_lesson_even_for_a_class_stored_with_some(world):
    client, store, bank = world
    path = client.get("/api/path", headers=auth()).json()
    assert len(path["lessons"]) == 24 and sum(len(l["skills"]) for l in path["lessons"]) == 96
    small = KID.replace("kid", "small")
    store.add_member(store.create_class("setup", "B", lessons=["t", "k"])["id"], small)
    assert len(client.get("/api/path", headers=auth(small)).json()["lessons"]) == 24


def test_a_student_of_two_classes_sees_every_lesson_once_in_the_banks_order(world):
    client, store, bank = world
    two = "two@school.test"
    store.add_member(store.create_class("setup", "B", lessons=["k", "t"])["id"], two)
    store.add_member(store.create_class("setup", "C", lessons=["t2", "k"])["id"], two)
    assert [l["id"] for l in client.get("/api/path", headers=auth(two)).json()["lessons"]] == [l["id"] for l in bank.lessons_with_skills()]


def test_a_teacher_sees_every_lesson_and_a_manager_is_refused(world):
    client, _, _ = world
    assert len(client.get("/api/path", headers=auth(TEACHER)).json()["lessons"]) == 24
    assert client.get("/api/path", headers=auth(MGR)).status_code == 403


def test_the_path_gives_each_skill_its_state_and_the_goal_and_streak(world):
    client, _, bank = world
    bare = client.ids[0]
    path = client.get("/api/path", headers=auth()).json()
    assert {s["state"] for l in path["lessons"] for s in l["skills"]} == {"not_started"}
    assert path["today"] == {"done": 0, "goal": 5, "reached": False} and path["streak"] == 0
    for _ in range(3):
        respond(client, bank, bare)
    path = client.get("/api/path", headers=auth()).json()
    states = {s["id"]: s["state"] for l in path["lessons"] for s in l["skills"]}
    assert states[bare] == "learning" and path["today"]["done"] == 3
    assert set(path["lessons"][0]["skills"][0]) == {"id", "name", "short", "state", "faded"}


def test_streak_counts_days_with_five_correct(world):
    client, _, bank = world
    for day in (MON, TUE):
        client.set_time(day)
        for _ in range(5):
            respond(client, bank, client.ids[0])
    path = client.get("/api/path", headers=auth()).json()
    assert path["today"]["reached"] is True and path["streak"] == 2


def test_the_next_skill_marker_follows_the_students_last_work(world):
    client, _, bank = world
    first = client.get("/api/path", headers=auth()).json()["lessons"][0]["skills"][0]["id"]
    assert client.get("/api/path", headers=auth()).json()["next"] == first       # a new student: the first skill of the first lesson
    bare = client.ids[0]
    respond(client, bank, bare)
    assert client.get("/api/path", headers=auth()).json()["next"] == bare        # continuing where they left off
    master(client, bank, bare)
    after = client.get("/api/path", headers=auth()).json()["next"]
    assert after not in (None, bare)                                              # the last answer mastered it: the marker moves on


def test_the_marker_is_none_when_everything_is_mastered_and_never_hides_a_skill(world):
    client, store, _ = world
    for p in client.get("/api/path", headers=auth()).json()["lessons"]:
        for s in p["skills"]:
            store.save_progress(KID_ID, s["id"], started_at="then", mastered_at="then")
    path = client.get("/api/path", headers=auth()).json()
    assert path["next"] is None and sum(len(l["skills"]) for l in path["lessons"]) == 96


# --- the collection ---

def test_collection_lists_mastered_skills_and_completed_lessons(world):
    client, _, bank = world
    assert client.get("/api/collection", headers=auth()).json() == {"skills": [], "lessons": []}
    lesson = min((l for l in bank.lessons if all(s.get("questions") for s in bank.skills if s["unit"] == l["id"])),
                 key=lambda l: len([s for s in bank.skills if s["unit"] == l["id"]]))
    ids = [s["id"] for s in bank.skills if s["unit"] == lesson["id"]]
    assert len(ids) >= 2
    for skill_id in ids[:-1]:
        master(client, bank, skill_id)
    partial = client.get("/api/collection", headers=auth()).json()
    assert len(partial["skills"]) == len(ids) - 1 and partial["lessons"] == []
    master(client, bank, ids[-1])
    done = client.get("/api/collection", headers=auth()).json()
    assert [l["id"] for l in done["lessons"]] == [lesson["id"]] and done["lessons"][0]["skills"] == len(ids)
    path = client.get("/api/path", headers=auth()).json()
    assert next(l for l in path["lessons"] if l["id"] == lesson["id"])["completed"] is True


def test_a_new_mastery_appears_in_the_collection(world):
    client, _, bank = world
    bare = client.ids[0]
    master(client, bank, bare)
    skills = client.get("/api/collection", headers=auth()).json()["skills"]
    assert [s["id"] for s in skills] == [bare] and skills[0]["lesson_name"] and skills[0]["mastered_at"]


def test_students_do_not_see_each_others_progress(world):
    client, store, bank = world
    store.add_member(store.get_class(1)["id"], OTHER)
    bare = client.ids[0]
    master(client, bank, bare)
    assert client.get("/api/collection", headers=auth(OTHER)).json() == {"skills": [], "lessons": []}
    assert open_skill(client, bare, OTHER)["state"] == "not_started"
    assert client.get("/api/path", headers=auth(OTHER)).json()["next"] == client.get("/api/path", headers=auth(OTHER)).json()["lessons"][0]["skills"][0]["id"]


# --- ten-question-rounds: practice is a round of ten questions, each once ---

def play_round(client, bank, skill_id, rights):
    """Answer the skill's round with the given right/wrong flags, one per question; return the answers' responses and the keys shown."""
    shown, out = [], []
    for ok in rights:
        shown.append(open_skill(client, skill_id)["question"]["key"])
        out.append(respond(client, bank, skill_id, correct=ok))
    return out, shown


def test_a_round_is_the_first_ten_questions_each_once_then_a_result_and_no_next_question(world):
    client, store, bank = world
    big = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 30)
    first_ten = set(bank.question_keys(big)[:10])
    assert len(bank.practice_keys(big)) == 10 and len(bank.question_keys(big)) == 30
    rights = [True, True, False, True, False, True, True, True, False, True]            # 7 right, 3 wrong
    answers, shown = play_round(client, bank, big, rights)
    assert len(shown) == 10 and set(shown) == first_ten                                  # each of the ten once, none of the other twenty
    assert [a["round"]["answered"] for a in answers] == list(range(1, 11)) and answers[-1]["round"]["results"] == rights
    assert all(a["next_question"] is not None for a in answers[:-1]) and answers[-1]["next_question"] is None
    last = answers[-1]["round"]
    assert last["done"] is True and last["result"]["right"] == 7 and last["result"]["total"] == 10 and len(last["result"]["missed"]) == 3
    from mathly2 import quiz
    drawn = {q["key"] for seed in range(20) for q in quiz.draw(bank, bank.skill(big)["unit"], rng=__import__("random").Random(seed))}
    assert drawn - first_ten                                                              # quizzes still draw the other twenty


def test_a_wrong_question_does_not_come_back_in_the_round(world):
    client, _, bank = world
    small = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 10)
    wrong = respond(client, bank, small, correct=False)
    missed_key = open_skill(client, small)["round"]                                       # (the question missed is the one just answered)
    keys = []
    nxt = wrong["next_question"]
    while nxt:
        keys.append(nxt["key"])
        nxt = respond(client, bank, small)["next_question"]
    assert len(keys) == 9 and len(set(keys)) == 9 and missed_key["results"] == [False]
    assert len({*keys}) == 9 and open_skill(client, small)["question"] is None


def test_the_result_has_no_right_answers_and_shows_each_wrong_question_with_its_mistake(world):
    client, _, bank = world
    small = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 10)
    answers, _ = play_round(client, bank, small, [False] * 4 + [True] * 6)
    result = answers[-1]["round"]["result"]
    assert result["right"] == 6 and len(result["missed"]) == 4
    assert all(m["question"] and (m["mistake"] is None or m["mistake"]["name"]) for m in result["missed"])
    blob = __import__("json").dumps(answers[-1], ensure_ascii=False)
    assert '"correct": true' not in blob.split('"round"')[1]                              # the round's result carries no right choice


def test_leaving_in_the_middle_continues_the_round_and_a_finished_round_shows_its_result_again(world):
    client, _, bank = world
    small = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 10)
    play_round(client, bank, small, [True, False, True, True])                            # leave after four
    back = open_skill(client, small)
    assert back["round"]["answered"] == 4 and back["round"]["results"] == [True, False, True, True] and back["question"] is not None
    play_round(client, bank, small, [True] * 6)
    done = open_skill(client, small)
    assert done["question"] is None and done["round"]["done"] and done["round"]["result"]["right"] == 9      # the result again


def test_a_new_round_starts_all_ten_again_with_empty_dots_and_mastery_counts_across_rounds(world):
    client, _, bank = world
    small = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 10)
    play_round(client, bank, small, [True] * 10)
    assert client.post(f"/api/skills/{small}/round", headers=auth()).status_code == 200
    fresh = open_skill(client, small)
    assert fresh["question"] is not None and fresh["round"]["answered"] == 0 and fresh["round"]["results"] == [] and not fresh["round"]["done"]
    client.set_time(TUE)                                                                  # the second day, in the new round
    answered = respond(client, bank, small)
    assert answered["state"] == "mastered" and answered["mastered_now"] is True            # 3 right in a row on two days, across the rounds


def test_a_new_round_before_the_round_is_done_changes_nothing_and_a_stale_answer_is_refused(world):
    client, _, bank = world
    small = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 10)
    shown = open_skill(client, small)["question"]["key"]
    client.post(f"/api/skills/{small}/round", headers=auth())
    assert open_skill(client, small)["question"]["key"] == shown
    play_round(client, bank, small, [True] * 10)
    late = client.post(f"/api/skills/{small}/answer", json={"question_key": shown, "choice": 0}, headers=auth())
    assert late.status_code == 409                                                        # the round is over: no question is on screen


def test_a_student_who_practised_before_rounds_begins_a_new_one(world):
    client, store, bank = world
    small = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 10)
    for key in bank.question_keys(small):                                                 # ten old answers, from before rounds
        store.add_answer(KID_ID, small, key, True, True, None, MON.date())
    store.save_progress(KID_ID, small, started_at="then", current_key=bank.question_keys(small)[0], current_helped=False)
    opened = open_skill(client, small)
    assert opened["question"] is not None and opened["round"]["answered"] == 0 and not opened["round"]["done"]
    assert store.get_progress(KID_ID, small)["round_start"] == 10
