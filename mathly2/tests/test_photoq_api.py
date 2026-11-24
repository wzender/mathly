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
    def __init__(self, readable=True, skill=None, score=80, fail=False, parts=False):
        self.readable, self.skill, self.score, self.fail, self.parts = readable, skill, score, fail, parts
        self.read, self.graded, self.tutored = [], [], []

    def read_question(self, image, skills, subject=""):
        self.read.append({"skills": [s["id"] for s in skills], "subject": subject, "bytes": len(image)})
        if self.fail:
            raise RuntimeError("down")
        if self.parts:
            return {"readable": True, "question": "נתון: △ABC שווה־שוקיים ($AB = AC$), ∠A₁ = 30°, PC = 18 ס\"מ.\nא. מצאו את ∠B.\nב. מצאו את BP.\nג. הוכיחו: FP = BC/6.",
                    "answer": "א. $∠B = 30°$\nב. $BP = 12$ ס\"מ\nג. הוכחה", "steps": ["א. $∠B = (180° − 120°)/2$", "ב. $AP = PC/2$", "ג. $FP = BP/2$"],
                    "skill": self.skill if self.skill is not None else skills[0]["id"]}
        return {"readable": self.readable, "question": "פתרו: $2x + 3 = 11$", "answer": "$x = 4$", "steps": ["$2x = 8$", "$x = 4$"],
                "skill": self.skill if self.skill is not None else skills[0]["id"]}

    def tutor_reply(self, context, history, message, board=None):
        self.tutored.append({"context": context, "history": len(history), "message": message, "board": bool(board)})
        if self.fail:
            raise RuntimeError("down")
        return "נסו לבודד את $x$: מה עושים קודם?"

    def grade_open(self, question, answer, typed, board):
        self.graded.append({"question": question, "answer": answer, "typed": typed, "board": len(board)})
        parts = [{"label": "א", "verdict": "correct", "feedback": "נכון"}, {"label": "ב", "verdict": "wrong", "feedback": "בדקו את $AP$"}] if self.parts else []
        return {"score": self.score, "verdict": "partial", "feedback": "דרך טובה, טעות בחילוק", "tip": "בדקו את החילוק", "parts": parts}


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



def help_(client, q, kind, text="", who=KID):
    return client.post(f"/api/photo-questions/{q['id']}/help", headers=auth(who), json={"kind": kind, "text": text})


def test_the_help_ladder_lowers_the_grade_it_can_reach_and_the_tutor_never_gets_ahead(world):
    q = photograph(world).json()
    assert q["help"]["max_grade"] == 100 and q["help"]["rungs"] == {"direction": 90, "step": 75, "full": 40}
    got = help_(world, q, "direction").json()["help"]
    assert got["max_grade"] == 90 and got["rungs"]["direction"] is None and [m["role"] for m in got["chat"]] == ["student", "ai"]
    got = help_(world, q, "step").json()["help"]
    assert got["max_grade"] == 75 and got["revealed"] == 1 and got["chat"][-1]["text"] == "צעד 1: $2x = 8$" and got["rungs"]["step"] == 65
    ask = help_(world, q, "ask", "למה מחסירים 3?").json()["help"]
    sent = world.app.state.reviewer.tutored[-1]
    assert sent["context"]["shown"] == 1 and sent["context"]["full"] is False and sent["board"] is False and sent["message"] == "למה מחסירים 3?"
    assert ask["chat"][-1]["role"] == "ai" and ask["max_grade"] == 75                         # a question costs nothing
    got = help_(world, q, "full").json()["help"]
    assert got["max_grade"] == 40 and got["full"] and "תשובה: $x = 4$" in got["chat"][-1]["text"] and got["rungs"] == {"direction": None, "step": None, "full": None}
    send_work(world, f"pq:{q['id']}", "q")
    done = world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={}).json()
    assert done["grade"] == 40 and done["review"]["raw"] == 80                                # the check said 80; help capped it at 40
    after = help_(world, q, "ask", "לא הבנתי את המשוב").json()
    sent = world.app.state.reviewer.tutored[-1]
    assert sent["context"]["full"] is True and sent["board"] is True and sent["context"]["review"]["feedback"]
    assert help_(world, q, "step").status_code == 409                                         # no rungs after the check
    teacher = world.get("/api/teaching/photo-questions", headers=auth(TEACHER)).json()[0]
    assert teacher["max_grade"] == 40 and len(teacher["chat"]) == len(after["help"]["chat"])   # the teacher sees the conversation


def test_help_has_limits_and_says_when_the_ai_is_down(world):
    from mathly2 import photoq
    q = photograph(world).json()
    assert help_(world, q, "ask", "  ").status_code == 422
    world.app.state.reviewer.fail = True
    assert help_(world, q, "ask", "עזרה").status_code == 503
    assert world.get(f"/api/photo-questions/{q['id']}", headers=auth(KID)).json()["help"]["chat"] == []     # nothing kept on a failure
    world.app.state.reviewer.fail = False
    for _ in range(photoq.MESSAGES_A_QUESTION):
        assert help_(world, q, "ask", "עוד שאלה").status_code == 200
    assert help_(world, q, "ask", "ועוד").status_code == 429


def test_latex_from_the_ai_is_shown_as_symbols_even_on_a_question_already_kept(world):
    q = photograph(world).json()
    world.store.save_photo_question(q["id"], question=r"נתון: \triangle ABC, \angle A_1 = 30^\circ. מצאו את \angle B.", answer=r"$\angle B = 75^\circ$",
                                    steps=[r"$\frac{180 - 30}{2} = 75$"], chat=[{"role": "ai", "text": r"חשבו את \angle B", "kind": "ask"}])
    got = world.get(f"/api/photo-questions/{q['id']}", headers=auth(KID)).json()
    assert got["question"] == "נתון: △ ABC, ∠ A₁ = 30°. מצאו את ∠ B." and got["help"]["chat"][0]["text"] == "חשבו את ∠ B"
    send_work(world, f"pq:{q['id']}", "q")
    world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={})
    teacher = world.get("/api/teaching/photo-questions", headers=auth(TEACHER)).json()[0]
    assert teacher["answer"] == "$∠ B = 75°$" and teacher["steps"] == ["$(180 - 30)/2 = 75$"] and "\\" not in json.dumps(teacher, ensure_ascii=False)


def test_a_question_with_sub_parts_has_a_box_a_part_and_feedback_a_part(world):
    world.app.state.reviewer.parts = True
    q = photograph(world).json()
    assert q["question"].count("\n") == 3 and q["final"] is None
    assert q["finals"] == [{"part": "א", "label": "∠B =", "unit": "°"}, {"part": "ב", "label": "BP =", "unit": 'ס"מ'}]   # no box for the proof
    send_work(world, f"pq:{q['id']}", "q")
    done = world.post(f"/api/photo-questions/{q['id']}/submit", headers=auth(KID), json={"typed": "א=30;ב=12"}).json()
    assert world.app.state.reviewer.graded[-1]["typed"] == "א=30;ב=12" and done["typed"] == "א=30;ב=12"
    assert [p["label"] for p in done["review"]["parts"]] == ["א", "ב"] and done["review"]["parts"][1]["verdict"] == "wrong"
    assert done["answer"].splitlines()[1] == 'ב. $BP = 12$ ס"מ'


def test_final_boxes_of_plain_answers():
    assert photoq.final_box("$x = 4$") == {"label": "x =", "unit": ""} and photoq.final_box("$75°$") == {"label": "", "unit": "°"}
    assert photoq.final_box('BP = 12 ס"מ') == {"label": "BP =", "unit": 'ס"מ'} and photoq.final_box("$x = 2y + 3$") is None
    assert photoq.finals("$x = 4$") == [{"part": "", "label": "x =", "unit": ""}] and photoq.parts_of("$x = 4$") == []
