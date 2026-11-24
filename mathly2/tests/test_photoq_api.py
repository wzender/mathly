"""Photographed questions (photoq.py): the phone's code, the AI's reading and check (a fake here), the board, the grade, and the teacher's
approval into the class's bank."""
import json

import pytest
from fastapi.testclient import TestClient

from mathly2 import photoq
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.test_boardwork_api import auth, png, send_work, uid

KID, KID2, TEACHER, OTHER_TEACHER = "kid@school.test", "kid2@school.test", "t@school.test", "t2@school.test"


class FakeAI:
    def __init__(self, readable=True, skill=None, score=80, fail=False):
        self.readable, self.skill, self.score, self.fail = readable, skill, score, fail
        self.read, self.graded = [], []

    def read_question(self, image, skills, subject=""):
        self.read.append({"skills": [s["id"] for s in skills], "subject": subject, "bytes": len(image)})
        if self.fail:
            raise RuntimeError("down")
        return {"readable": self.readable, "question": "פתרו: $2x + 3 = 11$", "answer": "$x = 4$", "steps": ["$2x = 8$", "$x = 4$"],
                "skill": self.skill if self.skill is not None else skills[0]["id"]}

    def grade_open(self, question, answer, typed, board):
        self.graded.append({"question": question, "answer": answer, "typed": typed, "board": len(board)})
        return {"score": self.score, "verdict": "partial", "feedback": "דרך טובה, טעות בחילוק", "tip": "בדקו את החילוק"}


@pytest.fixture
def world():
    bank, store = load_bank(), InMemoryStore()
    lessons = [l["id"] for l in bank.lessons][:3]
    a = store.create_class("setup", "ט", lessons=lessons, teacher_email=TEACHER)
    b = store.create_class("setup", "ח", lessons=lessons, teacher_email=OTHER_TEACHER)
    store.add_member(a["id"], KID)
    store.add_member(a["id"], KID2)
    app = create_app(Settings(teachers=frozenset({TEACHER, OTHER_TEACHER})), bank=bank, store=store, reviewer=FakeAI())
    app.state.run_photoq = lambda target, app_, *args: target(app_, *args)          # inline, not in a thread
    client = TestClient(app)
    for who in (KID, KID2, TEACHER, OTHER_TEACHER):
        client.get("/api/me", headers=auth(who))
    client.store, client.a = store, a
    return client


def photograph(client, who=KID):
    """The computer asks with a code; the phone sends the photo; the question is read."""
    req = client.post("/api/photo-requests", headers=auth(who), json={"purpose": "question", "device": "pc"})
    assert req.status_code == 201, req.text
    assert req.json()["purpose"] == "question" and req.json()["assignment_id"] is None
    phone = client.get("/api/photo-requests/open?device=phone", headers=auth(who)).json()
    assert phone[0]["title"] == "שאלה לצילום" and phone[0]["code"] == req.json()["code"]
    sent = client.post(f"/api/photo-requests/{req.json()['id']}/picture", content=png(), headers={**auth(who), "Content-Type": "image/png"})
    assert sent.status_code == 200 and sent.json()["state"] == "received"
    return client.post("/api/photo-questions", headers=auth(who), json={"picture_id": sent.json()["picture_id"]})


def test_a_photo_is_read_shown_without_the_answer_answered_on_the_board_and_graded(world):
    got = photograph(world)
    assert got.status_code == 201, got.text
    q = got.json()
    assert q["state"] == "ready" and "2x + 3 = 11" in q["question"] and q["suggested_skill"] and q["skill"]["id"] == q["suggested_skill"]
    assert "answer" not in q and "steps" not in q and "x = 4" not in json.dumps(q)            # nothing of the answer before the check
    assert q["final"] == {"label": "x =", "unit": ""} and q["skills"] and q["checks_left"] == photoq.CHECKS
    assert world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={}).status_code == 422          # the board first
    assert send_work(world, f"pq:{q['id']}", "q").status_code == 201
    done = world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={"skill_id": "", "typed": "4"}).json()
    assert done["state"] == "checked" and done["grade"] == 80 and done["review"]["verdict"] == "partial" and done["review"]["feedback"]
    assert done["skill"] is None and done["answer"] == "$x = 4$" and done["steps"] and done["bank"] == "pending"   # external, and to the teacher
    ai = world.app.state.reviewer
    assert ai.graded[-1]["typed"] == "4" and ai.graded[-1]["answer"] == "$x = 4$" and ai.graded[-1]["board"] > 0
    assert KID not in json.dumps(ai.read + ai.graded)                                         # no name or email goes to the AI


def test_the_teacher_approves_it_into_the_class_bank_and_a_classmate_solves_it(world):
    q = photograph(world).json()
    send_work(world, f"pq:{q['id']}", "q")
    world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={"skill_id": q["suggested_skill"]})
    assert world.get("/api/teaching/photo-questions", headers=auth(OTHER_TEACHER)).json() == []      # another class's teacher sees nothing
    pending = world.get("/api/teaching/photo-questions", headers=auth(TEACHER)).json()
    assert len(pending) == 1 and pending[0]["student"] == KID and pending[0]["answer"] == "$x = 4$" and pending[0]["board_id"]
    assert world.get(f"/api/pictures/{pending[0]['picture_id']}", headers=auth(TEACHER)).status_code == 200   # the teacher sees the photo
    assert world.post(f"/api/teaching/photo-questions/{q['id']}", headers=auth(OTHER_TEACHER), json={"action": "approve"}).status_code == 404
    other_skill = pending[0]["skills"][1]["id"]
    ok = world.post(f"/api/teaching/photo-questions/{q['id']}", headers=auth(TEACHER),
                    json={"action": "approve", "skill_id": other_skill, "question": "פתרו את המשוואה: $2x + 3 = 11$"}).json()
    assert ok["bank"] == "approved" and ok["skill"]["id"] == other_skill and ok["question"].startswith("פתרו את המשוואה")
    listed = world.get("/api/photo-questions", headers=auth(KID2)).json()
    assert listed["on"] is True and [b["id"] for b in listed["bank"]] == [q["id"]] and world.get("/api/photo-questions", headers=auth(KID)).json()["bank"] == []
    copy = world.post(f"/api/photo-questions/from-bank/{q['id']}", headers=auth(KID2)).json()
    assert copy["state"] == "ready" and copy["from_bank"] and copy["skill"]["id"] == other_skill and "answer" not in copy
    send_work(world, f"pq:{copy['id']}", "q", who=KID2)
    solved = world.post(f"/api/photo-questions/{copy['id']}/submit", headers=auth(KID2), json={"skill_id": other_skill}).json()
    assert solved["state"] == "checked" and solved["bank"] == "none"                          # a copy never goes to the teacher again
    assert world.get("/api/photo-questions", headers=auth(KID2)).json()["bank"][0]["solved"] is True


def test_unreadable_failed_limits_and_no_ai(world):
    world.app.state.reviewer.readable = False
    q = photograph(world).json()
    assert q["state"] == "unreadable" and "צלמו שוב" in q["reason"]
    world.app.state.reviewer.readable, world.app.state.reviewer.fail = True, True
    assert photograph(world).json()["state"] == "failed"
    world.app.state.reviewer.fail = False
    for _ in range(photoq.DAILY_LIMIT - 2):
        assert photograph(world).status_code == 201
    assert photograph(world).status_code == 429                                               # five a day
    world.app.state.reviewer = None
    assert world.get("/api/photo-questions", headers=auth(KID2)).json()["on"] is False
    assert photograph(world, KID2).status_code == 503


def test_a_question_is_handed_in_at_most_three_times_and_only_by_its_student(world):
    q = photograph(world).json()
    assert world.get(f"/api/photo-questions/{q['id']}", headers=auth(KID2)).status_code == 404
    send_work(world, f"pq:{q['id']}", "q")
    assert send_work(world, f"pq:{q['id']}", "q", who=KID2).status_code == 404
    for n in range(photoq.CHECKS):
        got = world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={})
        assert got.status_code == 200 and got.json()["checks_left"] == photoq.CHECKS - n - 1
    assert world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={}).status_code == 409
    assert world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={"skill_id": "nope"}).status_code in (409, 422)
