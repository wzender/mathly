"""The comets and the rule for when one is due (add-rewards 3.1)."""
from datetime import date

from mathly2 import comets
from mathly2.store import InMemoryStore
from mathly2.tests.test_store import Recorder, U, V

TODAY, YESTERDAY = date(2026, 11, 9), date(2026, 11, 8)


def test_there_are_twelve_comets_with_unique_ids_and_a_symbol_name_and_fact():
    assert len(comets.COMETS) == 12 and len(set(comets.IDS)) == 12
    assert all(c["sym"] and c["name"] and len(c["fact"]) > 20 for c in comets.COMETS)
    assert [c["name"] for c in comets.COMETS][:3] == ["פאי", "פיבונאצ׳י", "יחס הזהב"] and comets.get("pi")["sym"] == "π"
    assert comets.get("nope") is None


def test_all_caught_means_never_due():
    assert comets.due({"last_comet_day": YESTERDAY}, set(comets.IDS), TODAY, True, roll=0.0) is False


def test_at_most_one_comet_a_day():
    assert comets.due({"last_comet_day": TODAY}, set(), TODAY, True, roll=0.0) is False


def test_the_first_comet_comes_only_on_the_answer_that_reaches_the_goal():
    assert comets.due(None, set(), TODAY, goal_just_reached=False, roll=0.0) is False      # no chance roll before the first comet
    assert comets.due({"last_comet_day": None}, set(), TODAY, goal_just_reached=False, roll=0.0) is False
    assert comets.due(None, set(), TODAY, goal_just_reached=True, roll=0.99) is True        # certain, whatever the roll


def test_after_a_comet_was_offered_each_right_answer_has_a_12_percent_chance():
    state = {"last_comet_day": YESTERDAY}
    assert comets.due(state, {"pi"}, TODAY, False, roll=0.11) is True
    assert comets.due(state, {"pi"}, TODAY, False, roll=0.13) is False


def test_pick_gives_a_comet_the_student_does_not_have_and_none_when_all_are_held():
    held = set(comets.IDS[:11])
    assert comets.pick(held, roll=0.0)["id"] == comets.IDS[11]
    assert comets.pick(set(comets.IDS)) is None
    seen = {comets.pick({"pi"}, roll=i / 20)["id"] for i in range(20)}
    assert "pi" not in seen and len(seen) == 11


def test_store_remembers_caught_comets_and_the_reward_days_per_student():
    store = InMemoryStore()
    assert store.comets_of(U) == set() and store.reward_state(U) is None
    store.add_comet(U, "pi"); store.add_comet(U, "pi"); store.add_comet(V, "e")
    assert store.comets_of(U) == {"pi"} and store.comets_of(V) == {"e"}
    store.save_reward_state(U, last_comet_day=TODAY)
    store.save_reward_state(U, last_catch_day=TODAY)                     # the other field stays
    assert store.reward_state(U)["last_comet_day"] == TODAY and store.reward_state(U)["last_catch_day"] == TODAY
    assert store.reward_state(V) is None


def test_supabase_comet_and_reward_requests():
    s = Recorder([[{"comet_id": "pi"}], None, [{"user_id": U, "last_comet_day": "2026-11-09", "last_catch_day": None}],
                  [{"user_id": U, "last_comet_day": "2026-11-09", "last_catch_day": None}], []])
    assert s.comets_of(U) == {"pi"}
    s.add_comet(U, "e")
    assert s.calls[1][:2] == ("POST", "m2_comets") and s.calls[1][3] == {"user_id": U, "comet_id": "e"} and s.calls[1][5] is True
    assert s.reward_state(U) == {"user_id": U, "last_comet_day": TODAY, "last_catch_day": None}
    saved = s.save_reward_state(U, last_comet_day=TODAY)
    assert s.calls[3][3] == {"user_id": U, "last_comet_day": "2026-11-09"} and saved["last_comet_day"] == TODAY
    assert s.reward_state(V) is None
