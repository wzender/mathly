"""The work on the board: saved with every answer, seen and given points by the student's teacher (board-work 1.1-1.4)."""
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mathly2 import cleanup, clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.test_quizzes_api import right_index, skill_of

TEACHER, KID, OTHER_TEACHER, STRANGER = "t@school.test", "kid@school.test", "t2@school.test", "other@school.test"


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def uid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def png(color="white"):
    out = io.BytesIO()
    Image.new("RGB", (80, 50), color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def world():
    bank = load_bank()
    store = InMemoryStore()
    lessons = [l["id"] for l in bank.lessons][:3]
    mine = store.create_class("setup", "A", lessons=lessons, teacher_email=TEACHER)
    store.add_member(mine["id"], KID)
    store.add_member(store.create_class("setup", "B", lessons=lessons, teacher_email=OTHER_TEACHER)["id"], STRANGER)
    client = TestClient(create_app(Settings(teachers=frozenset({TEACHER, OTHER_TEACHER})), bank=bank, store=store))
    for who in (KID, STRANGER, TEACHER, OTHER_TEACHER):
        client.get("/api/me", headers=auth(who))                    # a first sign-in links the account to the class
    lesson = next(l for l in lessons if any(s["unit"] == l and bank.question_keys(s["id"]) for s in bank.skills))
    return client, store, bank, lesson


def send_work(client, ref, key, who=KID, data=None):
    return client.post(f"/api/work?ref={ref}&key={key}", content=data or png(), headers={**auth(who), "Content-Type": "image/png"})


def quiz(client, lesson, who=KID):
    response = client.post(f"/api/lessons/{lesson}/quiz/start", headers=auth(who))
    assert response.status_code == 200, response.text
    return response.json()


def choose(client, bank, attempt, key, right, who=KID):
    response = client.put(f"/api/attempts/{attempt['id']}/answers", headers=auth(who),
                          json={"key": key, "choice": right_index(bank, skill_of(key), key, right)})
    assert response.status_code == 200, response.text


def handed_in(client, bank, lesson, rights):
    attempt = quiz(client, lesson)
    for q, right in zip(attempt["questions"], rights):
        choose(client, bank, attempt, q["key"], right)
        assert send_work(client, attempt["id"], q["key"]).status_code == 201
    client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth(KID))
    return attempt


def test_a_quiz_says_work_is_required_and_lists_the_questions_whose_board_is_saved(world):
    client, store, bank, lesson = world
    attempt = quiz(client, lesson)
    assert attempt["work_required"] is True and attempt["work"] == []
    key = attempt["questions"][0]["key"]
    assert send_work(client, attempt["id"], key).status_code == 201
    assert quiz(client, lesson)["work"] == [key]
    picture = store.get_picture(store.work_of(uid(KID), attempt["id"])[key])
    assert picture["kind"] == "work" and picture["owner_id"] == uid(KID)


def test_work_goes_only_to_your_own_attempt_and_its_own_questions(world):
    client, _, bank, lesson = world
    attempt = quiz(client, lesson)
    assert send_work(client, attempt["id"], attempt["questions"][0]["key"], who=STRANGER).status_code == 404
    assert send_work(client, attempt["id"], "nope").status_code == 404
    assert send_work(client, attempt["id"], attempt["questions"][0]["key"], data=b"not a picture").status_code in (400, 415, 422)


def test_practice_work_is_kept_per_question_and_the_latest_wins(world):
    client, store, bank, lesson = world
    skill = next(s["id"] for s in bank.skills if s["unit"] == lesson and bank.question_keys(s["id"]))
    key = bank.question_keys(skill)[0]
    assert send_work(client, "practice", key).status_code == 201
    first = store.work_of(uid(KID), "practice")[key]
    assert send_work(client, "practice", key, data=png("yellow")).status_code == 201
    second = store.work_of(uid(KID), "practice")[key]
    assert first != second and store.picture_refs(first)["work"] == [] and store.picture_refs(second)["work"]
    assert send_work(client, "practice", "missing-key").status_code == 404


def test_the_class_teacher_sees_the_choices_and_the_board_and_others_do_not(world):
    client, store, bank, lesson = world
    attempt = handed_in(client, bank, lesson, [True] * 13 + [False] * 2)
    listed = client.get("/api/teaching/work", headers=auth(TEACHER)).json()
    assert [i["id"] for i in listed] == [attempt["id"]] and listed[0]["student"] == KID and listed[0]["checked"] is False and listed[0]["grade"] == 87
    assert client.get("/api/teaching/work", headers=auth(OTHER_TEACHER)).json() == []
    view = client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()
    q = view["questions"][0]
    assert sum(c["correct"] for c in q["choices"]) == 1 and q["picked"] is not None and q["auto"] == 1 and q["work"]
    assert client.get(f"/api/pictures/{q['work']}", headers=auth(TEACHER)).status_code == 200
    assert client.get(f"/api/pictures/{q['work']}", headers=auth(OTHER_TEACHER)).status_code == 404
    assert client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(OTHER_TEACHER)).status_code == 404
    assert client.get("/api/teaching/counts", headers=auth(TEACHER)).json()["work"] == 1


def test_points_for_the_way_recompute_the_grade(world):
    client, store, bank, lesson = world
    attempt = handed_in(client, bank, lesson, [True] * 12 + [False] * 3)                              # 80: not passed
    wrong = [q["key"] for q in attempt["questions"]][12:]
    right = attempt["questions"][0]["key"]
    post = lambda credit: client.post(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER), json={"credit": credit})
    got = post({wrong[0]: 1, wrong[1]: 0.5})
    assert got.status_code == 200 and got.json()["grade"] == 90 and got.json()["checked_at"]           # 13.5 of 15
    facts = client.get(f"/api/lessons/{lesson}/quiz", headers=auth(KID)).json()
    assert facts["best"] == 90                                                                         # the lesson's grade follows
    assert post({right: 0}).json()["grade"] == 83                                                      # a right answer with no way: 12.5 of 15
    assert post({right: None, wrong[1]: None}).json()["grade"] == 87                                   # back to automatic: 13 of 15
    assert post({wrong[2]: 0.3}).status_code == 422 and post({"nope": 1}).status_code == 422
    assert client.get("/api/teaching/work", headers=auth(TEACHER)).json()[0]["checked"] is True
    assert client.post(f"/api/teaching/work/{attempt['id']}", headers=auth(OTHER_TEACHER), json={"credit": {right: 1}}).status_code == 404


def test_an_open_quiz_is_not_on_the_teachers_list_and_a_replaced_board_is_cleaned_up(world):
    client, store, bank, lesson = world
    attempt = quiz(client, lesson)
    key = attempt["questions"][0]["key"]
    send_work(client, attempt["id"], key)
    old = store.work_of(uid(KID), attempt["id"])[key]
    send_work(client, attempt["id"], key, data=png("blue"))
    assert client.get("/api/teaching/work", headers=auth(TEACHER)).json() == []
    removed = cleanup.run(store, client.app.state.pictures, clock.now() + cleanup.retention.ORPHAN_AGE * 2)
    assert removed["orphans"] == 1 and store.get_picture(old)["deleted_at"] and not store.get_picture(store.work_of(uid(KID), attempt["id"])[key])["deleted_at"]
