"""The AI review of the way in a practice test or the simulation (board-review). The reviewer is a fake; GeminiReviewer is tested with its
HTTP call replaced."""
import io
import json
import urllib.error
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from mathly2 import boardreview, clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.test_boardwork_api import KID, TEACHER, auth, png, send_work, uid
from mathly2.tests.test_quizzes_api import right_index, skill_of


class FakeReviewer:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def review(self, items):
        self.calls.append(items)
        if self.fail:
            raise boardreview.ReviewFailure(self.fail)
        return {"summary": "דרך מסודרת. כדאי לבדוק סימנים.",
                "questions": [{"n": it["n"], "verdict": "partial", "feedback": f"בשאלה {it['n']} הטעות בשלב השני", "tip": "בדקו סימן"} for it in items]}


def make(reviewer):
    bank, store = load_bank(), InMemoryStore()
    lessons = [l["id"] for l in bank.lessons][:2]
    klass = store.create_class("setup", "A", lessons=lessons, teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    test = store.create_test(klass["id"], clock.school_day() + timedelta(days=9), lessons, TEACHER, created_at=clock.now() - timedelta(days=20))
    app = create_app(Settings(teachers=frozenset({TEACHER})), bank=bank, store=store, reviewer=reviewer)
    app.state.run_review = boardreview.run                                       # inline, not in a thread
    client = TestClient(app)
    client.get("/api/me", headers=auth(KID))
    client.get("/api/me", headers=auth(TEACHER))
    return client, store, bank, test, lessons


def hand_in(client, bank, test, boards=2, path=None):
    started = client.post(path or f"/api/tests/{test['id']}/exercise/1/start?all_skills=true", headers=auth(KID))
    assert started.status_code == 200, started.text
    attempt = started.json()
    for i, q in enumerate(attempt["questions"]):
        client.put(f"/api/attempts/{attempt['id']}/answers", headers=auth(KID), json={"key": q["key"], "choice": right_index(bank, skill_of(q["key"]), q["key"], i % 2 == 0)})
        if i < boards:
            assert send_work(client, attempt["id"], q["key"]).status_code == 201
    return attempt, client.post(f"/api/attempts/{attempt['id']}/submit", headers=auth(KID)).json()


def test_handing_in_a_practice_test_sends_its_boards_once_and_the_student_gets_the_review():
    fake = FakeReviewer()
    client, store, bank, test, _ = make(fake)
    attempt, result = hand_in(client, bank, test)
    assert len(fake.calls) == 1 and [it["n"] for it in fake.calls[0]] == [1, 2]                  # one request, only the questions with a board
    item = fake.calls[0][0]
    assert item["image"] and item["choices"] and isinstance(item["correct"], int) and KID not in json.dumps({k: v for k, v in item.items() if k != "image"})
    review = result["review"]
    assert review["state"] == "done" and review["summary"].startswith("דרך")
    first = attempt["questions"][0]["key"]
    assert set(review["questions"]) == {first, attempt["questions"][1]["key"]} and review["questions"][first]["verdict"] == "partial"
    assert result["keys"][0] == first
    again = client.get(f"/api/attempts/{attempt['id']}", headers=auth(KID)).json()
    assert again["review"] == review and len(fake.calls) == 1                                     # read again: not reviewed again
    teacher = client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()
    assert teacher["questions"][0]["ai"]["feedback"].startswith("בשאלה 1") and teacher["ai_summary"]


def test_a_lesson_quiz_is_not_reviewed_and_no_key_means_no_review():
    fake = FakeReviewer()
    client, store, bank, test, lessons = make(fake)
    lesson = next(l for l in lessons if any(s["unit"] == l and bank.question_keys(s["id"]) for s in bank.skills))
    _, result = hand_in(client, bank, test, path=f"/api/lessons/{lesson}/quiz/start")
    assert result["review"] is None and fake.calls == []
    client2, _, bank2, test2, _ = make(None)
    _, result2 = hand_in(client2, bank2, test2)
    assert result2["review"] is None


def test_a_failed_review_is_shown_as_failed_and_a_test_with_no_board_needs_no_call():
    client, store, bank, test, _ = make(FakeReviewer(fail="rate_limited"))
    attempt, result = hand_in(client, bank, test)
    assert result["review"] == {"state": "failed"}
    assert store.get_attempt(attempt["id"])["review"]["reason"] == "rate_limited"
    fake = FakeReviewer()
    client, store, bank, test, _ = make(fake)
    _, result = hand_in(client, bank, test, boards=0)
    assert result["review"]["state"] == "done" and result["review"]["questions"] == {} and fake.calls == []


def test_a_review_lost_by_a_restart_is_started_again():
    fake = FakeReviewer()
    client, store, bank, test, _ = make(fake)
    attempt, _ = hand_in(client, bank, test)
    store.save_attempt(attempt["id"], review={"state": "pending", "at": (clock.now() - timedelta(minutes=30)).isoformat()})
    assert client.get(f"/api/attempts/{attempt['id']}", headers=auth(KID)).json()["review"]["state"] == "done" and len(fake.calls) == 2


# ---- the Gemini client itself ----

def items():
    return [{"n": 3, "question": "$x^2=9$", "choices": ["3", "±3"], "correct": 1, "picked": 0, "image": png()}]


def answer(payload):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(payload)}]}}]}


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(body))


def test_gemini_reviewer_sends_one_request_with_the_picture_and_retries_when_told_to_wait():
    waits, sent = [], []
    reviewer = boardreview.GeminiReviewer("key", sleep=waits.append)
    replies = [http_error(429, json.dumps({"error": {"details": [{"retryDelay": "7s"}]}}).encode()),
               answer({"summary": "s", "questions": [{"n": 3, "verdict": "wrong", "feedback": "f", "tip": "t"}]})]

    def call(body):
        sent.append(json.loads(body))
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    reviewer._call = call
    got = reviewer.review(items())
    assert got["questions"][0]["verdict"] == "wrong" and waits == [8.0] and len(sent) == 2
    parts = sent[0]["contents"][0]["parts"]
    assert any("inline_data" in p for p in parts) and "לא לגלות" in json.dumps(parts, ensure_ascii=False)
    assert sent[0]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize("code,reason", [(400, "bad_request"), (403, "permission"), (404, "model_not_found")])
def test_gemini_errors_have_reasons(code, reason):
    reviewer = boardreview.GeminiReviewer("key", sleep=lambda s: None)
    reviewer._call = lambda body: (_ for _ in ()).throw(http_error(code))
    with pytest.raises(boardreview.ReviewFailure) as caught:
        reviewer.review(items())
    assert caught.value.reason == reason


def test_gemini_bad_or_cut_output_is_a_failure():
    reviewer = boardreview.GeminiReviewer("key")
    reviewer._call = lambda body: {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]}
    with pytest.raises(boardreview.ReviewFailure) as caught:
        reviewer.review(items())
    assert caught.value.reason == "incomplete"
    reviewer._call = lambda body: {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not json"}]}}]}
    with pytest.raises(boardreview.ReviewFailure) as caught:
        reviewer.review(items())
    assert caught.value.reason == "bad_output"
