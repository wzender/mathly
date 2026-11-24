"""The AI tutor on a practice question (practice_tutor.py): it guides before the answer (which then does not count), explains after it,
never gets a name, and has a daily limit."""
import json

import pytest
from fastapi.testclient import TestClient

from mathly2 import practice_tutor
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.test_boardwork_api import auth
from mathly2.tests.test_photoq_api import FakeAI

KID = "kid@school.test"


@pytest.fixture
def world():
    practice_tutor._counts.clear()
    bank, store = load_bank(), InMemoryStore()
    lessons = [l["id"] for l in bank.lessons][:3]
    klass = store.create_class("setup", "ט", lessons=lessons, teacher_email="t@school.test")
    store.add_member(klass["id"], KID)
    ai = FakeAI()
    client = TestClient(create_app(Settings(teachers=frozenset({"t@school.test"})), bank=bank, store=store, reviewer=ai))
    client.get("/api/me", headers=auth(KID))
    client.ai, client.bank = ai, bank
    client.skill = next(s["id"] for s in bank.skills if s["unit"] in lessons and bank.practice_keys(s["id"]))
    return client


def ask(client, key, message="איך מתחילים?", history=()):
    return client.post(f"/api/skills/{client.skill}/tutor", headers=auth(KID), json={"question_key": key, "message": message, "history": list(history)})


def wrong_choice(client, key):
    served = client.bank.practice_question(client.skill, key)
    return next(c["index"] for c in served["choices"] if not client.bank.grade(client.skill, key, c["index"])["correct"])


def test_before_the_answer_it_guides_and_the_answer_does_not_count(world):
    opened = world.get(f"/api/skills/{world.skill}", headers=auth(KID)).json()
    assert opened["tutor"] is True
    key = opened["question"]["key"]
    got = ask(world, key, history=[{"role": "student", "text": "שלום"}, {"role": "ai", "text": "שלום!"}])
    assert got.status_code == 200, got.text
    assert got.json()["helped"] is True and got.json()["reply"] and got.json()["left"] == practice_tutor.MESSAGES_A_DAY - 1
    sent = world.ai.tutored[-1]
    assert sent["context"]["full"] is False and "עוד לא ענה" in sent["context"]["note"] and sent["history"] == 2 and not sent["board"]
    assert "התשובות לבחירה" in sent["context"]["question"] and sent["context"]["answer"]                  # the right answer: for the AI only
    assert KID not in json.dumps(world.ai.tutored, ensure_ascii=False)
    done = world.post(f"/api/skills/{world.skill}/answer", headers=auth(KID), json={"question_key": key, "choice": wrong_choice(world, key)})
    assert done.status_code == 200


def test_after_a_wrong_answer_it_explains_with_the_mistake(world):
    key = world.get(f"/api/skills/{world.skill}", headers=auth(KID)).json()["question"]["key"]
    world.post(f"/api/skills/{world.skill}/answer", headers=auth(KID), json={"question_key": key, "choice": wrong_choice(world, key)})
    got = ask(world, key, "למה טעיתי?").json()
    sent = world.ai.tutored[-1]
    assert got["helped"] is False and sent["context"]["full"] is True and sent["context"]["review"]["verdict"] == "wrong"
    assert "כבר ענה" in sent["context"]["note"]
    other = next(k for k in world.bank.practice_keys(world.skill) if k != key and k != world.get(f"/api/skills/{world.skill}", headers=auth(KID)).json()["question"]["key"])
    assert ask(world, other).status_code == 409                                                              # neither on screen nor answered


def test_a_helped_answer_is_not_counted(world):
    key = world.get(f"/api/skills/{world.skill}", headers=auth(KID)).json()["question"]["key"]
    ask(world, key)
    right = next(c["index"] for c in world.bank.practice_question(world.skill, key)["choices"] if world.bank.grade(world.skill, key, c["index"])["correct"])
    done = world.post(f"/api/skills/{world.skill}/answer", headers=auth(KID), json={"question_key": key, "choice": right}).json()
    assert done["correct"] is True and done["correct_in_row"] == 0                                         # right, but it does not count


def test_limits_and_no_ai(world):
    key = world.get(f"/api/skills/{world.skill}", headers=auth(KID)).json()["question"]["key"]
    assert ask(world, key, "   ").status_code == 422
    assert ask(world, "no-such-key").status_code == 404
    world.ai.fail = True
    assert ask(world, key).status_code == 503
    world.ai.fail = False
    for _ in range(practice_tutor.MESSAGES_A_DAY):
        assert ask(world, key).status_code == 200
    assert ask(world, key).status_code == 429
    world.app.state.reviewer = None
    assert world.get(f"/api/skills/{world.skill}", headers=auth(KID)).json()["tutor"] is False
    assert ask(world, key).status_code == 503
