"""AI help (add-ai-help 2.1, 2.2): the queue, the student's requests, sending, budgets, failures, usage and privacy."""
import io
import threading
import time
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mathly2 import ai, ai_help, clock, pictures
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

T, T2, DEV, MGR = "t@school.test", "t2@school.test", "dev@school.test", "mgr@school.test"
KID, KID2, OUT, TWO = "kid@school.test", "kid2@school.test", "out@school.test", "two@school.test"
uid = lambda email: str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
auth = lambda email: {"Authorization": f"Bearer dev:{email}"}


def jpeg(color="white"):
    out = io.BytesIO()
    Image.new("RGB", (60, 40), color).save(out, "JPEG")
    return out.getvalue()


@pytest.fixture(scope="module")
def bank():
    return load_bank()


class World:
    pass


@pytest.fixture
def w(bank, monkeypatch):
    """Class A (teacher T, AI on, 5 checks a day; KID, KID2, TWO), class B (teacher T2, AI off; OUT); TWO is also in class C (AI on, teacher T2)."""
    world = World()
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    quiz_lesson = next(u["id"] for u in bank.data["units"] if u.get("quiz"))
    world.a = store.create_class("setup", "A", lessons=[quiz_lesson], teacher_email=T, ai_enabled=True, ai_daily_checks=5)
    world.b = store.create_class("setup", "B", lessons=[quiz_lesson], teacher_email=T2, ai_enabled=False)
    world.c = store.create_class("setup", "C", lessons=[quiz_lesson], teacher_email=T2, ai_enabled=True, ai_daily_checks=5)
    for email in (KID, KID2, TWO):
        store.add_member(world.a["id"], email)
    store.add_member(world.b["id"], OUT)
    store.add_member(world.c["id"], TWO)
    for email in (KID, KID2, OUT, TWO):
        store.link_user(email, uid(email))
    world.store, world.quiz_lesson, world.bank = store, quiz_lesson, bank
    world.fake = ai.FakeAI()
    world.pics = pictures.MemoryPictures()
    world.client = TestClient(create_app(Settings(developers=frozenset({DEV})), bank=bank, store=store, picture_store=world.pics, ai_client=world.fake))
    moment = {"now": clock.now()}
    return world


def post_photo(w, who, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return w.client.post("/api/ai/photo" + (f"?{q}" if q else ""), content=jpeg(), headers={**auth(who), "Content-Type": "image/jpeg"})


def get(w, who, rid):
    return w.client.get(f"/api/ai/requests/{rid}", headers=auth(who)).json()


def wait(w, who, rid, states=("done", "failed"), timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        got = get(w, who, rid)
        if got["state"] in states:
            return got
        time.sleep(0.02)
    raise AssertionError(f"still {got['state']}")


def send(w, who, rid):
    return w.client.post(f"/api/ai/requests/{rid}/send", headers=auth(who))


def hand_in(w, email=KID, cls=None, title="דף", state="handed_in"):
    cls = cls or w.a
    row = w.store.create_assignment(cls["id"], title, clock.school_day() + timedelta(days=5), T, "quiz", quiz_lesson=w.quiz_lesson, created_at=clock.now())
    pic = pictures.store_picture(w.store, w.pics, uid(email), "answer", jpeg("blue"))
    w.store.save_submission(row["id"], uid(email), pictures=[pic["id"]], state="handed_in", late=False, handed_at=clock.now(), grade=None, teacher_note="")
    if state != "handed_in":
        w.store.save_submission(row["id"], uid(email), state="graded", grade=70, checked_at=clock.now(), checked_by=T)
    return row


# ---- a student's request waits; the AI is not called ----

def test_a_photo_becomes_a_waiting_request_and_the_ai_is_not_called(w):
    got = post_photo(w, KID)
    assert got.status_code == 201
    body = got.json()
    assert body["state"] == "waiting" and body["kind"] == "photo" and body["class"]["id"] == w.a["id"] and body["picture"]["id"]
    assert w.fake.calls == []
    assert [p["kind"] for p in w.store.pictures()] == ["help"]
    assert w.client.get("/api/ai/requests", headers=auth(KID)).json()[0]["id"] == body["id"]


def test_the_ai_off_refuses_a_students_request(w):
    assert post_photo(w, OUT).status_code == 409
    assert w.store.pictures() == []
    row = hand_in(w, OUT, w.b)
    assert w.client.post(f"/api/assignments/{row['id']}/ai-check", headers=auth(OUT)).status_code == 409


def test_a_student_has_at_most_five_waiting_and_twenty_photos_a_day(w):
    for _ in range(5):
        assert post_photo(w, KID).status_code == 201
    refused = post_photo(w, KID)
    assert refused.status_code == 429 and "5" in refused.json()["detail"]
    for r in w.store.ai_requests(user_id=uid(KID2)):
        pass
    for i in range(20):                                                                   # twenty photos already today, none waiting
        pic = pictures.store_picture(w.store, w.pics, uid(KID2), "help", jpeg())
        w.store.create_ai_request("photo", uid(KID2), w.a["id"], picture_id=pic["id"], created_at=clock.now())
        w.store.save_ai_request(w.store.ai_requests(user_id=uid(KID2))[-1]["id"], state="declined")
    twenty = post_photo(w, KID2)
    assert twenty.status_code == 429 and "20" in twenty.json()["detail"]


def test_a_student_in_two_classes_goes_to_the_nearest_test_else_the_last_used_and_can_choose(w):
    assert post_photo(w, TWO).json()["class"]["id"] == w.a["id"]                          # no test anywhere: the first
    w.store.create_test(w.c["id"], clock.school_day() + timedelta(days=4), [w.quiz_lesson], T2, created_at=clock.now())
    w.store.create_test(w.a["id"], clock.school_day() + timedelta(days=9), [w.quiz_lesson], T, created_at=clock.now())
    assert post_photo(w, TWO).json()["class"]["id"] == w.c["id"]                          # the nearest test
    assert post_photo(w, TWO, class_id=w.a["id"]).json()["class"]["id"] == w.a["id"]       # or the student's choice
    assert post_photo(w, TWO, class_id=w.b["id"]).status_code == 409                       # not a class of theirs with the AI on


def test_cancelling_deletes_the_photo_and_only_a_waiting_request_of_your_own_can_be_cancelled(w):
    rid = post_photo(w, KID).json()["id"]
    assert w.client.post(f"/api/ai/requests/{rid}/cancel", headers=auth(KID2)).status_code == 404
    done = w.client.post(f"/api/ai/requests/{rid}/cancel", headers=auth(KID))
    assert done.status_code == 200 and done.json()["state"] == "cancelled" and done.json()["picture"] is None
    assert all(p["deleted_at"] for p in w.store.pictures(include_deleted=True))
    assert w.client.post(f"/api/ai/requests/{rid}/cancel", headers=auth(KID)).status_code == 409


def test_a_decline_with_a_note_shows_to_the_student_and_deletes_the_photo(w):
    rid = post_photo(w, KID).json()["id"]
    assert w.client.post(f"/api/ai/requests/{rid}/decline", json={"note": "צלמו שוב, יותר קרוב"}, headers=auth(T2)).status_code == 404   # not their class
    assert w.client.post(f"/api/ai/requests/{rid}/decline", json={"note": "צלמו שוב, יותר קרוב"}, headers=auth(T)).status_code == 200
    mine = get(w, KID, rid)
    assert mine["state"] == "declined" and mine["teacher_note"] == "צלמו שוב, יותר קרוב" and mine["picture"] is None and w.fake.calls == []


# ---- the teacher's queue ----

def test_who_sees_the_queue(w):
    rid = post_photo(w, KID).json()["id"]
    mine = w.client.get("/api/ai/queue", headers=auth(T)).json()
    assert mine["waiting"] == 1 and mine["items"][0]["id"] == rid and mine["items"][0]["student"] == KID and mine["own"]["allowance"] == 3
    assert w.client.get("/api/ai/queue", headers=auth(T2)).json()["waiting"] == 0                 # another teacher's classes only
    assert w.client.get("/api/ai/queue", headers=auth(DEV)).json()["waiting"] == 1 and w.client.get("/api/ai/queue", headers=auth(DEV)).json()["own"] is None
    assert w.client.get("/api/ai/queue", headers=auth(MGR)).status_code == 403 and w.client.get("/api/ai/queue", headers=auth(KID)).status_code == 403
    assert send(w, T2, rid).status_code == 404 and send(w, KID, rid).status_code == 403


def test_sending_runs_the_ai_and_the_student_gets_the_hints_the_photo_is_deleted_and_the_usage_recorded(w):
    rid = post_photo(w, KID, skill_id=w.bank.skills[0]["id"]).json()["id"]
    sent = send(w, T, rid)
    assert sent.status_code == 200 and sent.json()["state"] in ("processing", "done")
    done = wait(w, KID, rid)
    assert done["state"] == "done" and [s["hint"] for s in done["result"]["steps"]][0] and done["result"]["answer"] == "$x = 2$" and done["picture"] is None
    assert w.fake.calls[0][0] == "solve" and w.fake.calls[0][1][:2] == b"\xff\xd8" and w.fake.calls[0][2] == "image/jpeg"
    usage = w.store.ai_usage_rows()
    assert len(usage) == 1 and usage[0]["feature"] == "photo" and usage[0]["cost_usd"] > 0 and usage[0]["request_id"] == rid
    assert w.store.ai_allowance_used(f"class:{w.a['id']}", clock.school_day()) == 1
    assert all(p["deleted_at"] for p in w.store.pictures(include_deleted=True))                  # not kept
    assert send(w, T, rid).status_code == 409                                                  # already handled


def test_a_teacher_sends_her_own_photo_at_once_with_three_a_day_and_a_developer_without_a_limit(w):
    for _ in range(3):
        got = post_photo(w, T)
        assert got.status_code == 201 and got.json()["state"] in ("processing", "done") and got.json()["class"] is None
        wait(w, T, got.json()["id"])
    over = post_photo(w, T)
    assert over.status_code == 429 and "3" in over.json()["detail"]
    assert not [p for p in w.store.pictures() if not p["deleted_at"]] and len(w.store.ai_requests(user_id=uid(T))) == 4                  # none kept; the refused one is cancelled
    for _ in range(5):
        assert post_photo(w, DEV).status_code == 201


def test_a_batch_sends_what_the_budget_allows_and_the_rest_waits(w):
    for who in (KID, KID2, TWO):
        for _ in range(3):
            post_photo(w, who, class_id=w.a["id"])
    w.store.update_class(w.a["id"], ai_daily_checks=4)
    got = w.client.post("/api/ai/batch", json={"scope": "photos", "class_id": w.a["id"]}, headers=auth(T)).json()
    assert got["sent"] == 4 and got["left"] == 5 and got["short"] is True and "מחר" in got["message"]
    assert len(w.store.ai_requests(states=["waiting"])) == 5
    first_four = [r["id"] for r in w.store.ai_requests(kinds=["photo"])][:4]
    assert all(r["sent_by"] == T for r in w.store.ai_requests() if r["id"] in first_four)              # oldest first


def test_two_sends_at_once_with_one_check_left_send_exactly_one(w):
    w.store.update_class(w.a["id"], ai_daily_checks=1)
    ids = [post_photo(w, KID).json()["id"], post_photo(w, KID2).json()["id"]]
    codes = []

    def go(rid):
        codes.append(send(w, T, rid).status_code)
    threads = [threading.Thread(target=go, args=(r,)) for r in ids]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [200, 429] and w.store.ai_allowance_used(f"class:{w.a['id']}", clock.school_day()) == 1


# ---- failures ----

@pytest.mark.parametrize("reason", sorted(set(ai.FAILURES) - {"api_key_missing"}))
def test_a_failed_call_is_given_back_shows_its_cause_to_the_teacher_and_a_short_message_to_the_student(w, reason):
    w.fake.fail = reason
    rid = post_photo(w, KID).json()["id"]
    send(w, T, rid)
    seen_by_teacher = wait(w, T, rid)
    assert seen_by_teacher["state"] == "failed" and seen_by_teacher["failure"]["reason"] == reason and seen_by_teacher["failure"]["todo"] and seen_by_teacher["failure"]["detail"] == "fake"
    seen_by_student = get(w, KID, rid)
    assert seen_by_student["failure"] == {"message": ai.STUDENT_MESSAGE} and "reason" not in str(seen_by_student["failure"])
    assert w.store.ai_allowance_used(f"class:{w.a['id']}", clock.school_day()) == 0                  # given back
    assert w.store.ai_usage_rows() == []
    assert [p for p in w.store.pictures() if not p["deleted_at"]]                                   # kept for the retry
    w.fake.fail = None
    assert send(w, T, rid).status_code == 200 and wait(w, T, rid)["state"] == "done"                 # a retry


def test_without_a_key_a_send_fails_with_the_reason_the_teacher_can_act_on(bank):
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=["t"], teacher_email=T, ai_enabled=True)
    store.add_member(klass["id"], KID)
    store.link_user(KID, uid(KID))
    client = TestClient(create_app(Settings(), bank=bank, store=store))                           # no ANTHROPIC_API_KEY
    rid = client.post("/api/ai/photo", content=jpeg(), headers={**auth(KID), "Content-Type": "image/jpeg"}).json()["id"]
    client.post(f"/api/ai/requests/{rid}/send", headers=auth(T))
    end = time.time() + 5
    while time.time() < end and client.get(f"/api/ai/requests/{rid}", headers=auth(T)).json()["state"] == "processing":
        time.sleep(0.02)
    got = client.get(f"/api/ai/requests/{rid}", headers=auth(T)).json()
    assert got["state"] == "failed" and got["failure"]["reason"] == "api_key_missing" and "ANTHROPIC_API_KEY" in got["failure"]["todo"]


def test_a_photo_the_ai_could_not_read_is_given_back_but_still_shown(w, bank):
    class Blurry(ai.FakeAI):
        def solve(self, image, media_type, skills):
            out = super().solve(image, media_type, skills)
            return {**out, "readable": False, "note": "צלמו שוב"}
    w.client.app.state.ai = Blurry()
    rid = post_photo(w, KID).json()["id"]
    send(w, T, rid)
    done = wait(w, KID, rid)
    assert done["state"] == "done" and done["result"]["readable"] is False and done["result"]["note"] == "צלמו שוב"
    assert w.store.ai_allowance_used(f"class:{w.a['id']}", clock.school_day()) == 0


def test_a_restart_returns_processing_requests_to_waiting(w):
    rid = post_photo(w, KID).json()["id"]
    w.store.start_ai_request(rid, T, clock.now())
    assert ai_help.requeue_after_restart(w.store) == 1 and get(w, KID, rid)["state"] == "waiting"


# ---- checking a handed-in answer ----

def test_a_student_asks_for_a_check_it_waits_the_teacher_sends_and_sees_it_as_a_suggestion(w):
    row = hand_in(w)
    asked = w.client.post(f"/api/assignments/{row['id']}/ai-check", headers=auth(KID))
    assert asked.status_code == 201 and asked.json()["state"] == "waiting" and w.fake.calls == []
    assert w.client.post(f"/api/assignments/{row['id']}/ai-check", headers=auth(KID)).status_code == 409           # one at a time
    rid = asked.json()["id"]
    send(w, T, rid)
    done = wait(w, KID, rid)
    assert done["state"] == "done" and done["result"]["score"] == 100 and done["result"]["feedback"] and "solution" not in done["result"]
    kind, images, snapshot = w.fake.calls[0]
    assert kind == "check" and [label for label, _ in images][-1] == "תשובת התלמיד" and snapshot["title"] == "דף" and snapshot["quiz"]["questions"]
    payload = str(snapshot) + str([label for label, _ in images])
    assert "@" not in payload and KID not in payload and "kid" not in payload                                          # no name, no email
    inbox = w.client.get(f"/api/submissions/{w.store.get_submission(row['id'], uid(KID))['id']}", headers=auth(T)).json()
    assert inbox["ai"]["result"]["score"] == 100 and inbox["ai"]["result"]["solution"] and inbox["grade"] is None


def test_the_teachers_grade_wins_and_the_ai_check_is_kept_beside_it(w):
    row = hand_in(w)
    rid = w.client.post(f"/api/assignments/{row['id']}/ai-check", headers=auth(KID)).json()["id"]
    send(w, T, rid)
    wait(w, KID, rid)
    sub = w.store.get_submission(row["id"], uid(KID))
    graded = w.client.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 60, "note": "פחות", "seen": sub["handed_at"].isoformat()}, headers=auth(T))
    assert graded.status_code == 200 and graded.json()["grade"] == 60
    assert w.store.get_ai_request(rid)["result"]["score"] == 100                                                        # the AI's check is never edited
    assert w.client.get(f"/api/submissions/{sub['id']}", headers=auth(T)).json()["ai"]["result"]["score"] == 100


def test_an_unreadable_answer_has_no_score_and_the_teacher_is_told(w):
    w.fake.check_result = {"readable": False, "confident": False, "answer_correct": False, "reasoning_correct": False, "drawing_correct": False,
                           "units_correct": False, "complete": False, "transcription": "", "feedback": "לא קריא", "next_step": "", "solution": "", "score": 0}
    row = hand_in(w)
    sub = w.store.get_submission(row["id"], uid(KID))
    got = w.client.post(f"/api/submissions/{sub['id']}/ai-check", headers=auth(T))                                      # the teacher asks: sent at once
    assert got.status_code == 201
    done = wait(w, T, got.json()["id"])
    assert done["result"]["score"] is None and done["result"]["verdict"] == "unreadable"
    assert w.store.ai_allowance_used(f"class:{w.a['id']}", clock.school_day()) == 0                                       # given back


def test_checks_come_only_for_a_handed_in_answer_of_the_students_own_assignment(w):
    row = hand_in(w, state="graded")
    assert w.client.post(f"/api/assignments/{row['id']}/ai-check", headers=auth(KID)).status_code == 409
    other = hand_in(w, KID2, title="אחר")
    assert w.client.post(f"/api/assignments/{other['id']}/ai-check", headers=auth(KID)).status_code == 409            # a class assignment, but KID handed nothing in
    sub = w.store.get_submission(other["id"], uid(KID2))
    assert w.client.post(f"/api/submissions/{sub['id']}/ai-check", headers=auth(T2)).status_code == 404


# ---- asking the teacher to look again ----

def test_looking_again_one_open_per_answer_five_per_student_shows_in_the_inbox_and_closes_when_graded(w):
    row = hand_in(w, state="graded")
    asked = w.client.post(f"/api/assignments/{row['id']}/look-again", headers=auth(KID))
    assert asked.status_code == 201 and asked.json()["kind"] == "again" and w.fake.calls == []
    assert w.client.post(f"/api/assignments/{row['id']}/look-again", headers=auth(KID)).status_code == 409
    inbox = w.client.get("/api/teaching/inbox", headers=auth(T)).json()
    assert [i["kind"] for i in inbox] == ["again"] and inbox[0]["student"] == KID
    sub = w.store.get_submission(row["id"], uid(KID))
    again = w.client.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 85, "note": "צדקתם", "seen": sub["handed_at"].isoformat()}, headers=auth(T))
    assert again.status_code == 200 and again.json()["grade"] == 85
    assert w.store.get_ai_request(asked.json()["id"])["state"] == "closed" and w.client.get("/api/teaching/inbox", headers=auth(T)).json() == []
    assert w.client.post(f"/api/assignments/{row['id']}/look-again", headers=auth(KID)).status_code == 201             # a new one after it closed
    others = [hand_in(w, KID, title=f"עוד {i}", state="graded") for i in range(6)]
    codes = [w.client.post(f"/api/assignments/{o['id']}/look-again", headers=auth(KID)).status_code for o in others]
    assert codes.count(201) == 4 and codes.count(429) == 2                                                             # five open in all


def test_looking_again_needs_a_check_first(w):
    row = hand_in(w)
    assert w.client.post(f"/api/assignments/{row['id']}/look-again", headers=auth(KID)).status_code == 409


def test_a_checked_answer_with_no_request_cannot_be_graded_again(w):
    row = hand_in(w, state="graded")
    sub = w.store.get_submission(row["id"], uid(KID))
    refused = w.client.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 10, "note": "", "seen": sub["handed_at"].isoformat()}, headers=auth(T))
    assert refused.status_code == 409


def test_a_students_assignment_says_what_they_can_do(w):
    row = hand_in(w)
    mine = lambda: next(a for a in w.client.get("/api/assignments", headers=auth(KID)).json() if a["id"] == row["id"])
    assert mine()["ai"]["can_check"] is True and mine()["ai"]["can_look_again"] is False
    rid = w.client.post(f"/api/assignments/{row['id']}/ai-check", headers=auth(KID)).json()["id"]
    assert mine()["ai"]["can_check"] is False and mine()["ai"]["checks"][0]["state"] == "waiting"
    send(w, T, rid)
    wait(w, KID, rid)
    assert mine()["ai"]["can_look_again"] is True
