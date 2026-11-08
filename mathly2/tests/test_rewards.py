"""Rewards (add-rewards): the daily goal and streak, fading stars, comets. Helpers and the `world` fixture come from test_skills_api."""
from datetime import timedelta

from mathly2.tests.test_skills_api import (KID, KID_ID, MON, TUE, auth, master, open_skill, respond, right_choice, raw, world)  # noqa: F401

# --- 1.1 daily goal and streak ---


def path_of(client, who=KID):
    return client.get("/api/path", headers=auth(who)).json()


def test_a_fifth_right_answer_shows_the_goal_reached(world):
    client, _, bank = world
    bare = client.ids[0]
    for _ in range(4):
        respond(client, bank, bare)
    assert path_of(client)["today"] == {"done": 4, "goal": 5, "reached": False}
    assert respond(client, bank, bare)["today"]["reached"] is True
    assert path_of(client)["today"] == {"done": 5, "goal": 5, "reached": True}


def test_an_answer_given_after_help_counts_toward_the_goal(world):
    client, _, bank = world
    bare = client.ids[0]
    for _ in range(4):
        respond(client, bank, bare)
    client.post(f"/api/skills/{bare}/help", headers=auth())
    assert respond(client, bank, bare)["today"]["reached"] is True


def test_a_four_day_streak_still_shows_four_on_the_morning_with_no_answers(world):
    client, _, bank = world
    bare = client.ids[0]
    for offset in range(4):
        client.set_time(MON + timedelta(days=offset))
        for _ in range(5):
            respond(client, bank, bare)
    client.set_time(MON + timedelta(days=4))                     # the morning after: nothing answered yet
    path = path_of(client)
    assert path["today"]["done"] == 0 and path["streak"] == 4


def test_a_missed_day_restarts_the_streak_at_today(world):
    client, _, bank = world
    bare = client.ids[0]
    client.set_time(MON)
    for _ in range(5):
        respond(client, bank, bare)
    client.set_time(MON + timedelta(days=2))                     # yesterday (Tuesday) had no streak day
    assert path_of(client)["streak"] == 0
    for _ in range(5):
        respond(client, bank, bare)
    assert path_of(client)["streak"] == 1


# --- 2.2 fading stars (server) ---

def skill_row(client, skill_id):
    return next(s for lesson in path_of(client)["lessons"] for s in lesson["skills"] if s["id"] == skill_id)


def mastered_skill(client, bank):
    bare = client.ids[0]
    master(client, bank, bare)
    return bare


def test_a_mastered_skill_fades_after_14_days_and_stays_mastered(world):
    client, _, bank = world
    skill = mastered_skill(client, bank)                     # its last answer is on the second day of `master`
    last = client.get("/api/collection", headers=auth()).json()["skills"][0]
    assert last["faded"] is False
    client.set_time(TUE + timedelta(days=13))
    assert skill_row(client, skill)["faded"] is False
    for days in (14, 15):
        client.set_time(TUE + timedelta(days=days))
        row = skill_row(client, skill)
        assert row["faded"] is True and row["state"] == "mastered"
        assert client.get("/api/collection", headers=auth()).json()["skills"][0]["faded"] is True


def test_one_answer_right_or_wrong_relights_a_faded_star(world):
    client, _, bank = world
    skill = mastered_skill(client, bank)
    for correct, offset in ((True, 20), (False, 60)):
        client.set_time(TUE + timedelta(days=offset))
        assert skill_row(client, skill)["faded"] is True
        respond(client, bank, skill, correct=correct)
        row = skill_row(client, skill)
        assert row["faded"] is False and row["state"] == "mastered"     # even a wrong answer relights; mastery is not undone
    client.set_time(TUE + timedelta(days=60 + 14))
    assert skill_row(client, skill)["faded"] is True


def test_a_skill_that_is_not_mastered_is_never_faded(world):
    client, _, bank = world
    bare = client.ids[0]
    respond(client, bank, bare)
    client.set_time(MON + timedelta(days=100))
    row = skill_row(client, bare)
    assert row["state"] == "learning" and row["faded"] is False
    assert all(not s["faded"] for lesson in path_of(client)["lessons"] for s in lesson["skills"])


def test_fading_changes_nothing_that_counts(world):
    client, _, bank = world
    skill = mastered_skill(client, bank)
    before = path_of(client)
    strip = lambda p: [(l["id"], l["mastered"], l["completed"], [(s["id"], s["state"]) for s in l["skills"]]) for l in p["lessons"]]
    client.set_time(TUE + timedelta(days=30))
    after = path_of(client)
    assert skill_row(client, skill)["faded"] is True
    assert strip(before) == strip(after)                                  # state, the hub's mastered count and completion are the same
    assert open_skill(client, skill)["state"] == "mastered"


# --- 3.2 a comet is due: the answer response says so ---

def answers(client, bank, n, correct=True):
    return [respond(client, bank, client.ids[0], correct=correct) for _ in range(n)]


def test_the_first_comet_comes_on_the_fifth_right_answer_and_not_before(world):
    client, store, bank = world
    client.app.state.comet_roll = lambda: 0.0                    # the 12% roll would always win: only the first-comet rule is tested
    got = [r["comet"] for r in answers(client, bank, 5)]
    assert got == [False, False, False, False, True]
    assert store.reward_state(KID_ID)["last_comet_day"] is not None


def test_no_second_comet_the_same_day(world):
    client, _, bank = world
    client.app.state.comet_roll = lambda: 0.0
    answers(client, bank, 5)
    assert [r["comet"] for r in answers(client, bank, 4)] == [False] * 4


def test_a_wrong_answer_never_brings_a_comet(world):
    client, _, bank = world
    client.app.state.comet_roll = lambda: 0.0
    answers(client, bank, 4)
    wrong = respond(client, bank, client.ids[0], correct=False)
    assert wrong["comet"] is False
    assert respond(client, bank, client.ids[0])["comet"] is True          # the fifth right one is still the first comet


def test_a_reload_cannot_give_a_second_comet(world):
    client, _, bank = world
    client.app.state.comet_roll = lambda: 0.0
    answers(client, bank, 5)
    open_skill(client, client.ids[0]); open_skill(client, client.ids[0])
    client.get("/api/path", headers=auth())
    assert respond(client, bank, client.ids[0])["comet"] is False


def test_after_the_first_comet_a_right_answer_on_a_later_day_has_a_chance(world):
    client, _, bank = world
    client.app.state.comet_roll = lambda: 0.0
    answers(client, bank, 5)
    client.set_time(TUE)
    client.app.state.comet_roll = lambda: 0.5
    assert respond(client, bank, client.ids[0])["comet"] is False       # 50% roll: no
    client.app.state.comet_roll = lambda: 0.05
    assert respond(client, bank, client.ids[0])["comet"] is True        # 5% roll: yes, and not a goal answer


def test_no_comet_comes_once_all_twelve_are_caught(world):
    client, store, bank = world
    from mathly2 import comets
    for c in comets.IDS:
        store.add_comet(KID_ID, c)
    client.app.state.comet_roll = lambda: 0.0
    assert not any(r["comet"] for r in answers(client, bank, 6))


# --- 3.3 catching and listing ---

OTHER_KID = "second@school.test"


def offered(client, bank):
    client.app.state.comet_roll = lambda: 0.0
    answers(client, bank, 5)                                       # the fifth right answer brings the first comet


def catch(client, who=KID):
    return client.post("/api/comets/catch", headers=auth(who))


def test_a_catch_adds_a_comet_the_student_did_not_have_with_its_fact(world):
    client, store, bank = world
    store.add_comet(KID_ID, "pi")
    offered(client, bank)
    got = catch(client)
    assert got.status_code == 200
    comet = got.json()["comet"]
    assert comet["id"] != "pi" and comet["sym"] and comet["name"] and comet["fact"]
    assert store.comets_of(KID_ID) == {"pi", comet["id"]}


def test_two_catches_in_a_row_give_one_comet_and_a_409(world):
    client, store, bank = world
    offered(client, bank)
    assert catch(client).status_code == 200
    again = catch(client)
    assert again.status_code == 409 and len(store.comets_of(KID_ID)) == 1


def test_a_catch_with_no_comet_offered_today_is_refused(world):
    client, store, bank = world
    assert catch(client).status_code == 409                         # nothing crossed yet
    offered(client, bank)
    client.set_time(TUE)                                            # the next day the crossing is gone
    assert catch(client).status_code == 409 and store.comets_of(KID_ID) == set()


def test_all_twelve_can_be_caught_over_twelve_days_and_the_list_shows_them(world):
    client, _, bank = world
    client.app.state.comet_roll = lambda: 0.0
    seen = set()
    for day in range(12):
        client.set_time(MON + timedelta(days=day))
        if day == 0:
            answers(client, bank, 5)
        else:
            client.app.state.comet_roll = lambda: 0.0                # 0.0 < 12%: a comet crosses on the first right answer of the day
            assert respond(client, bank, client.ids[0])["comet"] is True
        seen.add(catch(client).json()["comet"]["id"])
    assert len(seen) == 12
    listed = client.get("/api/comets", headers=auth()).json()
    assert listed["caught"] == 12 and listed["total"] == 12 and all(c["caught"] for c in listed["comets"])
    client.set_time(MON + timedelta(days=13))
    assert respond(client, bank, client.ids[0])["comet"] is False    # all caught: no more comets


def test_the_list_gives_facts_only_for_caught_comets_and_is_per_student(world):
    client, store, bank = world
    store.add_comet(KID_ID, "pi")
    store.add_comet(KID_ID, "e")
    listed = client.get("/api/comets", headers=auth()).json()
    caught = [c for c in listed["comets"] if c["caught"]]
    assert [c["id"] for c in caught] == ["pi", "e"] and all(c["fact"] for c in caught)
    missing = [c for c in listed["comets"] if not c["caught"]]
    assert len(missing) == 10 and all(set(c) == {"id", "caught"} for c in missing)     # a missing comet's name and fact are not sent
    store.add_member(store.classes()[0]["id"], OTHER_KID)
    assert client.get("/api/comets", headers=auth(OTHER_KID)).json()["caught"] == 0
