"""Real tests through the API: the teacher's routes (add-test-readiness 2.1), and below the students' (2.2-2.4)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

TEACHER, OTHER_TEACHER, KID, KID2, MGR = "t@school.test", "t2@school.test", "kid@school.test", "kid2@school.test", "mgr@school.test"
MON = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def uid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture
def world(bank, monkeypatch):
    """(client, store, lessons): class A (teacher T, students KID and KID2) studies three 4-skill lessons; class B (teacher T2) one."""
    from collections import Counter
    sizes = Counter(s["unit"] for s in bank.skills if bank.question_keys(s["id"]))
    lessons = [l for l, c in sizes.items() if c == 4][:4]
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    a = store.create_class("setup", "A", lessons=lessons[:3], teacher_email=TEACHER)
    store.create_class("setup", "B", lessons=lessons[3:], teacher_email=OTHER_TEACHER)
    for email in (KID, KID2):
        store.add_member(a["id"], email)
    client = TestClient(create_app(Settings(), bank=bank, store=store))
    moment = {"now": MON}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    client.set_time = lambda value: moment.update(now=value)
    client.class_id = a["id"]
    return client, store, lessons


def set_test(client, lessons, days=14, who=TEACHER, class_id=None, **extra):
    day = (clock.now() + timedelta(days=days)).date().isoformat()
    return client.post(f"/api/classes/{class_id or client.class_id}/tests", json={"date": day, "lessons": lessons[:2], **extra}, headers=auth(who))


# --- 2.1 the teacher ---

def test_a_test_set_without_changing_length_has_12_questions_and_45_minutes(world):
    client, store, lessons = world
    got = set_test(client, lessons, note="פרק 3")
    assert got.status_code == 201
    test = got.json()
    assert test["questions"] == 12 and test["minutes"] == 45 and test["note"] == "פרק 3" and test["days_left"] == 14
    assert [l["id"] for l in test["lessons"]] == lessons[:2] and test["class"]["name"] == "A"
    assert test["simulation"] == {"taken": 0, "total": 2, "missing": [KID, KID2]}
    assert store.get_test(test["id"])["created_by"] == TEACHER


def test_the_length_can_be_changed_and_is_limited(world):
    client, _, lessons = world
    ok = set_test(client, lessons, questions=20, minutes=60).json()
    assert ok["questions"] == 20 and ok["minutes"] == 60
    for bad in ({"questions": 0}, {"questions": 41}, {"minutes": 4}, {"minutes": 181}):
        assert set_test(client, lessons, **bad).status_code == 422


def test_lessons_outside_the_class_and_a_past_date_are_refused(world):
    client, _, lessons = world
    foreign = client.post(f"/api/classes/{client.class_id}/tests", json={"date": "2026-12-01", "lessons": ["not-a-lesson"]}, headers=auth(TEACHER))
    assert foreign.status_code == 422                                           # a lesson the class does not study (see test_subjects_api)
    assert client.post(f"/api/classes/{client.class_id}/tests", json={"date": "2026-12-01", "lessons": []}, headers=auth(TEACHER)).status_code == 422
    assert set_test(client, lessons, days=-1).status_code == 422
    assert set_test(client, lessons, days=0).status_code == 201                # the test day itself is allowed


def test_a_teacher_of_another_class_gets_404_and_a_student_or_manager_is_refused(world):
    client, _, lessons = world
    assert set_test(client, lessons, who=OTHER_TEACHER).status_code == 404
    assert set_test(client, lessons, who=KID).status_code == 403
    assert set_test(client, lessons, who=MGR).status_code == 403
    test = set_test(client, lessons).json()
    assert client.put(f"/api/tests/{test['id']}", json={"note": "x"}, headers=auth(OTHER_TEACHER)).status_code == 404
    assert client.delete(f"/api/tests/{test['id']}", headers=auth(OTHER_TEACHER)).status_code == 404
    assert client.get("/api/teaching/tests", headers=auth(OTHER_TEACHER)).json()[0]["tests"] == []


def test_a_test_can_be_changed_before_its_date_and_the_countdown_follows(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=10).json()
    moved = client.put(f"/api/tests/{test['id']}", json={"date": (clock.now() + 12 * DAY).date().isoformat(), "note": "מועד ב", "questions": 15,
                                                         "minutes": 50, "lessons": lessons[:1]}, headers=auth(TEACHER))
    assert moved.status_code == 200
    body = moved.json()
    assert body["days_left"] == 12 and body["note"] == "מועד ב" and body["questions"] == 15 and body["minutes"] == 50 and len(body["lessons"]) == 1
    home = client.get("/api/home", headers=auth(KID)).json()                                    # every student's countdown follows the new date
    assert home["tests"][0]["days_left"] == 12


def test_a_test_cannot_be_changed_on_or_after_its_day(world):
    client, _, lessons = world
    test = set_test(client, lessons, days=2).json()
    client.set_time(MON + 2 * DAY)
    assert client.put(f"/api/tests/{test['id']}", json={"note": "late"}, headers=auth(TEACHER)).status_code == 409
    client.set_time(MON + DAY)
    assert client.put(f"/api/tests/{test['id']}", json={"date": "2026-10-01"}, headers=auth(TEACHER)).status_code == 422


def test_removing_a_test_hides_it_but_keeps_the_grades_already_earned(world):
    client, store, lessons = world
    test = set_test(client, lessons).json()
    row = store.create_attempt(uid(KID), "exercise_test", f"{test['id']}:1", clock.now(), clock.now() + timedelta(minutes=45), [])
    store.save_attempt(row["id"], submitted_at=clock.now(), grade=80)
    assert client.delete(f"/api/tests/{test['id']}", headers=auth(TEACHER)).status_code == 204
    assert client.get("/api/teaching/tests", headers=auth(TEACHER)).json()[0]["tests"] == []
    assert client.get("/api/home", headers=auth(KID)).json()["tests"] == []
    assert store.get_test(test["id"])["removed_at"] is not None and store.get_attempt(row["id"])["grade"] == 80
    assert client.delete(f"/api/tests/{test['id']}", headers=auth(TEACHER)).status_code == 404


def test_the_tests_tab_shows_who_took_the_simulation_and_names_those_who_did_not(world):
    client, store, lessons = world
    klass = client.class_id
    for i in range(23):                                                      # a class of 25
        store.add_member(klass, f"s{i}@school.test")
    test = set_test(client, lessons).json()
    for i in range(22):
        row = store.create_attempt(uid(f"s{i}@school.test"), "simulation", str(test["id"]), clock.now(), clock.now() + timedelta(minutes=45), [])
        store.save_attempt(row["id"], submitted_at=clock.now(), grade=70)
        store.link_user(f"s{i}@school.test", uid(f"s{i}@school.test"))
    tab = client.get("/api/teaching/tests", headers=auth(TEACHER)).json()
    listed = tab[0]["tests"][0]
    assert listed["simulation"]["taken"] == 22 and listed["simulation"]["total"] == 25
    assert sorted(listed["simulation"]["missing"]) == sorted([KID, KID2, "s22@school.test"])
    taken = next(s for s in listed["students"] if s["email"] == "s0@school.test")
    assert taken["simulation_taken"] is True and taken["readiness"]["parts"]["S"] == 70
    assert [c["class"]["name"] for c in tab] == ["A"] and tab[0]["class"]["lessons"]


# --- 2.2 the student's home and a test's card ---

def covered(bank, lessons):
    return [s["id"] for s in bank.skills if s["unit"] in lessons and bank.question_keys(s["id"])]


def master(store, skills, who=KID):
    for i in skills:
        store.save_progress(uid(who), i, started_at="then", mastered_at="then")


def finished(store, test_id, kind, scope, grade, who=KID, questions=None):
    row = store.create_attempt(uid(who), kind, scope, clock.now() - 2 * DAY, clock.now() - 2 * DAY + timedelta(minutes=45), questions or [])
    return store.save_attempt(row["id"], submitted_at=clock.now() - 2 * DAY + timedelta(minutes=10), grade=grade)


def test_with_no_test_home_has_only_the_next_skill(world):
    client, _, _ = world
    home = client.get("/api/home", headers=auth(KID)).json()
    assert home["tests"] == [] and home["task"] is None and home["required_simulations"] == []
    assert home["next_skill"]["id"] and home["next_skill"]["name"]


def test_nine_days_before_the_test_todays_task_is_exercise_test_1(world):
    client, _, lessons = world
    test = set_test(client, lessons, days=9).json()
    home = client.get("/api/home", headers=auth(KID)).json()
    assert home["task"]["kind"] == "ex1" and home["task"]["test_id"] == test["id"]
    assert home["tests"][0]["days_left"] == 9 and home["tests"][0]["exercise_tests"][0]["best"] is None


def test_twelve_days_ahead_the_task_is_finishing_the_path_with_the_next_covered_skill(world):
    client, _, lessons = world
    set_test(client, lessons, days=12)
    task = client.get("/api/home", headers=auth(KID)).json()["task"]
    assert task["kind"] == "path" and task["skill"] and task["skill_name"]


def test_four_days_before_the_simulation_is_required_until_it_is_taken(world):
    client, store, lessons = world
    set_test_ = set_test(client, lessons, days=14).json()
    client.set_time(MON + 10 * DAY)                                          # four days left
    home = client.get("/api/home", headers=auth(KID)).json()
    assert home["task"]["kind"] == "sim" and [r["test_id"] for r in home["required_simulations"]] == [set_test_["id"]]
    assert home["tests"][0]["simulation"]["required"] is True and home["tests"][0]["simulation"]["open_now"] is True
    finished(store, set_test_["id"], "simulation", str(set_test_["id"]), 70)
    home = client.get("/api/home", headers=auth(KID)).json()
    assert home["required_simulations"] == [] and home["tests"][0]["simulation"]["taken"] is True and home["tests"][0]["simulation"]["grade"] == 70


def test_two_tests_give_the_task_of_the_closer_one(world):
    client, _, lessons = world
    far = set_test(client, lessons, days=10).json()
    near = set_test(client, lessons, days=4).json()
    home = client.get("/api/home", headers=auth(KID)).json()
    assert [t["id"] for t in home["tests"]] == [near["id"], far["id"]]
    assert home["task"]["test_id"] == near["id"] and home["task"]["kind"] == "ex1"       # set 4 days ahead: the short plan starts with exercise test 1 today


def test_readiness_shows_the_parts_that_exist_and_caps_before_the_simulation(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14).json()
    skills = covered(client.app.state.bank, lessons[:2])
    master(store, skills[:6])                                                # M = 6 of 8 = 75
    home = client.get("/api/home", headers=auth(KID)).json()["tests"][0]["readiness"]
    assert home["number"] == 75 and home["parts"] == {"M": 75, "E": None, "S": None} and home["waiting_for_simulation"] is True
    finished(store, test["id"], "exercise_test", f"{test['id']}:1", 60)
    finished(store, test["id"], "exercise_test", f"{test['id']}:2", 80)
    ready = client.get("/api/home", headers=auth(KID)).json()["tests"][0]["readiness"]
    assert ready["parts"] == {"M": 75, "E": 70, "S": None} and ready["number"] == 74       # (50*75 + 20*70) / 70
    master(store, skills[6:])
    finished(store, test["id"], "simulation", str(test["id"]), 90)
    full = client.get("/api/home", headers=auth(KID)).json()["tests"][0]["readiness"]
    assert full["parts"] == {"M": 100, "E": 70, "S": 90} and full["number"] == 91 and full["capped"] is False and full["label"] == "מוכנים"


def test_the_card_has_the_plan_the_exercise_tests_and_what_to_practise_first(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14).json()
    skills = covered(client.app.state.bank, lessons[:2])
    master(store, skills[:2])
    store.save_progress(uid(KID), skills[2], started_at="then")              # learning; the other five are not started
    card = client.get(f"/api/tests/{test['id']}", headers=auth(KID)).json()
    assert [s["id"] for s in card["plan"]] == ["path", "ex1", "ex2", "sim", "review"] and card["plan"][1]["day"] == 9
    assert [e["number"] for e in card["exercise_tests"]] == [1, 2] and card["questions"] == 12 and card["minutes"] == 45
    assert [s["id"] for s in card["practice_first"]] == skills[3:] and all(s["name"] for s in card["practice_first"])
    sim = card["simulation"]
    assert sim["open_now"] is False and sim["opens_in_days"] == 9 and sim["opens_on"] == (clock.now() + 9 * DAY).date().isoformat() and sim["taken"] is False


def test_a_student_of_another_class_and_a_missing_test_give_404(world):
    client, store, lessons = world
    test = set_test(client, lessons).json()
    store.add_member(store.classes()[1]["id"], "outsider@school.test")
    assert client.get(f"/api/tests/{test['id']}", headers=auth("outsider@school.test")).status_code == 404
    assert client.get("/api/tests/999", headers=auth(KID)).status_code == 404
    assert client.get("/api/home", headers=auth("outsider@school.test")).json()["tests"] == []


# --- 2.3 exercise tests and the simulation ---

import json  # noqa: E402


def right_index(bank, ref_key, right=True):
    skill_id = ref_key.split(":")[0]
    question = bank._questions[skill_id][ref_key]
    picks = [i for i, c in enumerate(question["choices"]) if bool(c.get("correct")) == right]
    if not right:
        picks = [i for i in picks if question["choices"][i].get("mistake")] or picks
    return picks[0]


def answer_all(client, bank, attempt, rights, who=KID):
    """Answer the attempt's questions right (True) or wrong (False), one flag per question; submit; return the result."""
    for question, ok in zip(attempt["questions"], rights):
        got = client.put(f"/api/attempts/{attempt['id']}/answers", json={"key": question["key"], "choice": right_index(bank, question["key"], ok)}, headers=auth(who))
        assert got.status_code == 200
    return client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth(who)).json()


def started(client, store, lessons, learning=5, mastered=3, who=KID):
    skills = covered(client.app.state.bank, lessons[:2])
    for i in skills[:learning]:
        store.save_progress(uid(who), i, started_at="then")
    master(store, skills[learning:learning + mastered], who)
    return skills


def start_ex(client, test_id, number=1, who=KID):
    return client.post(f"/api/tests/{test_id}/exercise/{number}/start", headers=auth(who))


def start_sim(client, test_id, who=KID):
    return client.post(f"/api/tests/{test_id}/simulation/start", headers=auth(who))


def test_an_exercise_test_has_the_tests_questions_and_time_and_no_right_answers_or_skill_names(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6, minutes=30).json()
    skills = started(client, store, lessons)
    got = start_ex(client, test["id"])
    assert got.status_code == 200
    attempt = got.json()
    assert attempt["kind"] == "exercise_test" and attempt["state"] == "open" and len(attempt["questions"]) == 6
    assert attempt["due_at"] is None                                                       # only the simulation is timed
    assert attempt["test"]["id"] == test["id"] and attempt["test"]["number"] == 1
    blob = json.dumps(attempt, ensure_ascii=False)
    assert '"correct"' not in blob and '"mistake"' not in blob and '"skill' not in blob
    assert not any(client.app.state.bank.skill(i)["name"] in blob for i in skills[:3])


def test_an_exercise_test_can_start_early_and_resumes_while_open(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14).json()
    started(client, store, lessons)
    client.set_time(MON + 3 * DAY)                                            # 11 days before the test
    first = start_ex(client, test["id"]).json()
    again = start_ex(client, test["id"]).json()
    assert first["id"] == again["id"] and [q["key"] for q in first["questions"]] == [q["key"] for q in again["questions"]]
    assert start_ex(client, test["id"], 2).json()["id"] != first["id"]        # exercise test 2 is its own attempt


def test_a_retake_draws_new_questions_and_the_best_grade_counts(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6).json()
    started(client, store, lessons)
    first = start_ex(client, test["id"]).json()
    keys = {q["key"] for q in first["questions"]}
    low = answer_all(client, client.app.state.bank, first, [True, True, False, False, False, False])
    assert low["grade"] == 33 and low["kind"] == "exercise_test"
    second = start_ex(client, test["id"]).json()
    assert second["id"] != first["id"] and not keys & {q["key"] for q in second["questions"]}
    high = answer_all(client, client.app.state.bank, second, [True] * 6)
    assert high["grade"] == 100
    card = client.get(f"/api/tests/{test['id']}", headers=auth(KID)).json()
    assert card["exercise_tests"][0]["best"] == 100 and card["exercise_tests"][0]["attempts"] == 2
    answer_all(client, client.app.state.bank, start_ex(client, test["id"]).json(), [False] * 6)       # a worse third try
    assert client.get(f"/api/tests/{test['id']}", headers=auth(KID)).json()["exercise_tests"][0]["best"] == 100


def test_the_result_links_the_weak_skills_found_without_right_answers(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6).json()
    started(client, store, lessons)
    result = answer_all(client, client.app.state.bank, start_ex(client, test["id"]).json(), [False] * 6)
    assert result["lost_skills"] and all(s["id"] and s["name"] for s in result["lost_skills"]) and '"correct"' not in json.dumps(result)


def test_an_exercise_test_with_nothing_started_draws_all_the_material_and_a_weak_skill_is_remembered(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6).json()
    got = start_ex(client, test["id"])
    assert got.status_code == 200 and len(got.json()["questions"]) == 6             # not refused: drawn like the simulation
    assert start_ex(client, test["id"], 3).status_code == 404


def test_an_exercise_test_with_all_skills_starts_even_when_nothing_is_started(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6).json()
    got = client.post(f"/api/tests/{test['id']}/exercise/1/start?all_skills=true", headers=auth(KID))
    assert got.status_code == 200 and len(got.json()["questions"]) == 6
    bank, lessons_of_test = client.app.state.bank, set(lessons[:2])
    assert all(bank.skill(q["skill_id"])["unit"] in lessons_of_test for q in store.get_attempt(got.json()["id"])["questions"])


def test_the_simulation_is_refused_8_days_before_with_its_opening_date(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14).json()
    started(client, store, lessons)
    client.set_time(MON + 6 * DAY)                                            # 8 days left; it opens 5 days before the test
    early = start_sim(client, test["id"])
    assert early.status_code == 409 and "ייפתח" in early.json()["detail"]
    assert store.attempts_of(uid(KID), "simulation") == []                    # nothing was started


def test_the_simulation_with_nothing_started_is_refused_and_all_skills_is_the_bypass(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14).json()
    client.set_time(MON + 12 * DAY)                                           # two days left: open, and nothing practiced
    refused = start_sim(client, test["id"])
    assert refused.status_code == 409 and "עוד לא התחלתם" in refused.json()["detail"]
    got = client.post(f"/api/tests/{test['id']}/simulation/start?all_skills=true", headers=auth(KID))
    assert got.status_code == 200 and got.json()["kind"] == "simulation" and len(got.json()["questions"]) == 12
    assert start_sim(client, test["id"]).json()["id"] == got.json()["id"]     # then it resumes like any simulation


def test_the_simulation_has_the_tests_length_can_be_taken_once_and_shows_its_result_again(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14).json()                          # 12 questions, 45 minutes
    started(client, store, lessons)
    client.set_time(MON + 10 * DAY)                                           # four days left: open
    sim = start_sim(client, test["id"]).json()
    assert sim["kind"] == "simulation" and len(sim["questions"]) == 12
    assert datetime.fromisoformat(sim["due_at"]) - datetime.fromisoformat(sim["now"]) == timedelta(minutes=45)
    assert start_sim(client, test["id"]).json()["id"] == sim["id"]            # open: it resumes
    done = answer_all(client, client.app.state.bank, sim, [True] * 8 + [False] * 4)
    assert done["grade"] == 67
    again = start_sim(client, test["id"]).json()
    assert again["state"] == "submitted" and again["id"] == sim["id"] and again["grade"] == 67      # a second try shows the result
    assert len(store.attempts_of(uid(KID), "simulation")) == 1


def test_the_skills_the_simulation_failed_are_the_review_tasks_of_the_last_days(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14).json()
    started(client, store, lessons)
    client.set_time(MON + 10 * DAY)
    sim = start_sim(client, test["id"]).json()
    result = answer_all(client, client.app.state.bank, sim, [False] * 12)
    failed = [s["id"] for s in result["lost_skills"]]
    assert failed
    client.set_time(MON + 11 * DAY)                                           # three days left
    card = client.get(f"/api/tests/{test['id']}", headers=auth(KID)).json()
    assert [s["id"] for s in card["simulation"]["review"]] == failed and card["simulation"]["taken"] is True
    task = client.get("/api/home", headers=auth(KID)).json()["task"]
    assert task["kind"] == "review" and task["skill"] == failed[0] and task["skill_name"]
    # practising that skill after the simulation takes it off the list: the next failed one is the task
    store.add_answer(uid(KID), failed[0], "k", True, True, None, clock.school_day())
    after = client.get("/api/home", headers=auth(KID)).json()["task"]
    if len(failed) > 1:
        assert after["kind"] == "review" and after["skill"] == failed[1]
    else:
        assert after["kind"] == "mixed_review"


# --- 2.4 the grades ---

def test_the_grades_list_each_tests_best_exercise_grades_and_the_simulation(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6).json()
    started(client, store, lessons)
    assert client.get("/api/grades", headers=auth(KID)).json()["exercise_tests"] == []
    bank = client.app.state.bank
    answer_all(client, bank, start_ex(client, test["id"]).json(), [True] * 3 + [False] * 3)                  # 50
    answer_all(client, bank, start_ex(client, test["id"]).json(), [True] * 5 + [False])                      # 83
    answer_all(client, bank, start_ex(client, test["id"], 2).json(), [True] * 6)                             # 100
    client.set_time(MON + 10 * DAY)
    answer_all(client, bank, start_sim(client, test["id"]).json(), [True] * 3 + [False] * 3)                  # 50 (6 questions)
    got = client.get("/api/grades", headers=auth(KID)).json()
    assert [(g["number"], g["best"], g["attempts"]) for g in got["exercise_tests"]] == [(1, 83, 2), (2, 100, 1)]
    assert [(g["best"], g["attempts"]) for g in got["simulations"]] == [(50, 1)]
    assert got["exercise_tests"][0]["test"]["id"] == test["id"] and got["exercise_tests"][0]["test"]["lessons"] and got["quizzes"] == []


def test_a_removed_test_keeps_its_name_in_the_grades(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6).json()
    started(client, store, lessons)
    answer_all(client, client.app.state.bank, start_ex(client, test["id"]).json(), [True] * 6)
    client.delete(f"/api/tests/{test['id']}", headers=auth(TEACHER))
    grade = client.get("/api/grades", headers=auth(KID)).json()["exercise_tests"][0]
    assert grade["best"] == 100 and grade["test"]["removed"] is True and grade["test"]["lessons"] and grade["test"]["date"]


def test_another_students_grades_are_not_mine_and_an_unfinished_attempt_is_not_listed(world):
    client, store, lessons = world
    test = set_test(client, lessons, days=14, questions=6).json()
    started(client, store, lessons)
    started(client, store, lessons, who=KID2)
    answer_all(client, client.app.state.bank, start_ex(client, test["id"], who=KID2).json(), [True] * 6, who=KID2)
    start_ex(client, test["id"])                                                                              # mine is open, not finished
    assert client.get("/api/grades", headers=auth(KID)).json()["exercise_tests"] == []
    assert len(client.get("/api/grades", headers=auth(KID2)).json()["exercise_tests"]) == 1
