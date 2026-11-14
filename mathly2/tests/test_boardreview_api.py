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
        self.calls, self.fail, self.summaries = [], fail, []          # calls: the questions asked about, one request each

    def review_one(self, item, on_event=lambda step, **info: None):
        self.calls.append(item)
        if self.fail:
            raise boardreview.ReviewFailure(self.fail)
        return {"verdict": "partial", "feedback": f"בשאלה {item['n']} הטעות בשלב השני", "tip": "בדקו סימן"}

    def summarize(self, reviewed, on_event=lambda step, **info: None):
        self.summaries.append(reviewed)
        return "דרך מסודרת. כדאי לבדוק סימנים."


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
    assert [it["n"] for it in fake.calls] == [1, 2] and len(fake.summaries) == 1               # a request per question with a board, then a summary
    item = fake.calls[0]
    assert item["image"] and item["choices"] and isinstance(item["correct"], int) and KID not in json.dumps({k: v for k, v in item.items() if k != "image"})
    review = result["review"]
    assert review["state"] == "done" and review["summary"].startswith("דרך")
    first = attempt["questions"][0]["key"]
    assert set(review["questions"]) == {first, attempt["questions"][1]["key"]} and review["questions"][first]["verdict"] == "partial"
    assert result["keys"][0] == first
    again = client.get(f"/api/attempts/{attempt['id']}", headers=auth(KID)).json()
    assert again["review"] == review and len(fake.calls) == 2                                     # read again: not reviewed again
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
    assert client.get(f"/api/attempts/{attempt['id']}", headers=auth(KID)).json()["review"]["state"] == "done" and len(fake.calls) == 4


# ---- the Gemini client itself ----

def items():
    return [{"n": 3, "question": "$x^2=9$", "choices": ["3", "±3"], "correct": 1, "picked": 0, "image": png()}]


def answer(payload):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(payload)}]}}]}


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(body))


def test_gemini_reviewer_sends_one_request_with_the_picture_and_retries_when_told_to_wait():
    waits, sent = [], []
    reviewer = boardreview.GeminiReviewer("key", sleep=waits.append, gap=0)
    replies = [http_error(429, json.dumps({"error": {"details": [{"retryDelay": "7s"}]}}).encode()),
               answer({"verdict": "wrong", "feedback": "f", "tip": "t"})]

    def call(body):
        sent.append(json.loads(body))
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    reviewer._call = call
    got = reviewer.review_one(items()[0])
    assert got["verdict"] == "wrong" and waits == [8.0] and len(sent) == 2
    parts = sent[0]["contents"][0]["parts"]
    assert any("inline_data" in p for p in parts) and "לא לגלות" in json.dumps(parts, ensure_ascii=False)
    assert sent[0]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize("code,reason", [(400, "bad_request"), (403, "permission"), (404, "model_not_found")])
def test_gemini_errors_have_reasons(code, reason):
    reviewer = boardreview.GeminiReviewer("key", sleep=lambda s: None, gap=0)
    reviewer._call = lambda body: (_ for _ in ()).throw(http_error(code))
    reviewer._models = lambda: []                                                  # no other model to fall back to
    with pytest.raises(boardreview.ReviewFailure) as caught:
        reviewer.review_one(items()[0])
    assert caught.value.reason == reason


def test_gemini_bad_or_cut_output_is_a_failure():
    reviewer = boardreview.GeminiReviewer("key")
    reviewer._call = lambda body: {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]}
    with pytest.raises(boardreview.ReviewFailure) as caught:
        reviewer.review_one(items()[0])
    assert caught.value.reason == "incomplete"
    reviewer._call = lambda body: {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not json"}]}}]}
    with pytest.raises(boardreview.ReviewFailure) as caught:
        reviewer.review_one(items()[0])
    assert caught.value.reason == "bad_output"


def test_a_test_handed_in_before_the_key_was_set_is_reviewed_when_the_teacher_opens_it():
    fake = FakeReviewer()
    client, store, bank, test, _ = make(fake)
    client.app.state.reviewer = None                                              # handed in with no key: no review
    attempt, _ = hand_in(client, bank, test)
    assert store.get_attempt(attempt["id"]).get("review") is None
    client.app.state.reviewer = fake                                              # the key is set now
    got = client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()
    assert len(fake.calls) == 2 and got["ai_summary"] and any(q["ai"] for q in got["questions"])


def test_the_teacher_sees_the_ai_state_and_can_run_it_again_or_on_a_quiz():
    fake = FakeReviewer(fail="rate_limited")
    client, store, bank, test, _ = make(fake)
    attempt, _ = hand_in(client, bank, test)
    view = client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()
    assert {k: view["ai"][k] for k in ("available", "state", "reason", "summary")} == {"available": True, "state": "failed", "reason": "rate_limited", "summary": None}
    assert client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()["ai"]["state"] == "failed"   # opening does not retry
    fake.fail = None
    again = client.post(f"/api/teaching/work/{attempt['id']}/review", headers=auth(TEACHER)).json()
    assert again["ai"]["state"] == "done" and again["ai"]["summary"] and len(fake.calls) == 3      # the first stopped at "rate limited"
    lesson = test["lessons"][0]
    quiz = client.post(f"/api/lessons/{lesson}/quiz/start", headers=auth(KID)).json()
    for q in quiz["questions"]:
        client.put(f"/api/attempts/{quiz['id']}/answers", headers=auth(KID), json={"key": q["key"], "choice": 0})
    send_work(client, quiz["id"], quiz["questions"][0]["key"])
    client.post(f"/api/attempts/{quiz['id']}/submit", headers=auth(KID))
    assert client.get(f"/api/teaching/work/{quiz['id']}", headers=auth(TEACHER)).json()["ai"]["state"] is None   # a quiz: only when asked
    assert client.post(f"/api/teaching/work/{quiz['id']}/review", headers=auth(TEACHER)).json()["ai"]["state"] == "done"
    assert client.post(f"/api/teaching/work/{quiz['id']}/review", headers=auth(KID)).status_code == 403


def test_no_key_says_so_and_a_missing_column_does_not_break_the_result():
    client, store, bank, test, _ = make(None)
    attempt, result = hand_in(client, bank, test)
    assert client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()["ai"]["available"] is False
    assert client.post(f"/api/teaching/work/{attempt['id']}/review", headers=auth(TEACHER)).status_code == 409
    client.app.state.reviewer = FakeReviewer()
    real = store.save_attempt
    store.save_attempt = lambda i, **f: (_ for _ in ()).throw(RuntimeError("no column review")) if "review" in f else real(i, **f)
    got = client.get(f"/api/attempts/{attempt['id']}", headers=auth(KID))
    assert got.status_code == 200 and got.json()["review"] == {"state": "failed"}
    assert client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()["ai"]["reason"] == "database"


def test_a_model_not_found_falls_back_to_a_flash_model_the_key_has():
    reviewer = boardreview.GeminiReviewer("key", " models/gemini-9-flash ", gap=0)
    assert reviewer.model == "gemini-9-flash"                                      # a pasted name is cleaned
    reviewer._models = lambda: ["gemini-2.0-flash-lite", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-image",
                                "gemini-3.8-flash", "text-embedding-004"]
    used = []

    def call(body):
        used.append(reviewer.model)
        if reviewer.model == "gemini-9-flash":
            raise http_error(404)
        return answer({"verdict": "correct", "feedback": "f", "tip": "t"})
    reviewer._call = call
    assert reviewer.review_one(items()[0])["verdict"] == "correct"
    assert used == ["gemini-9-flash", "gemini-3.8-flash"] and reviewer.model == "gemini-3.8-flash"


def test_pick_model_prefers_stable_full_and_new():
    assert boardreview.pick_model(["gemini-3-flash-preview", "gemini-2.5-flash-lite", "gemini-2.5-flash"]) == "gemini-2.5-flash"
    assert boardreview.pick_model(["gemini-2.5-pro", "gemini-2.5-flash-preview-tts"]) is None


def test_while_it_runs_the_review_stores_its_steps_for_the_screens():
    seen = []

    class Watching(FakeReviewer):
        def review_one(self, item, on_event=lambda step, **info: None):
            seen.append(boardreview.student_view(store.get_attempt(attempt_id)))
            on_event("busy", seconds=8)
            seen.append(boardreview.student_view(store.get_attempt(attempt_id)))
            return super().review_one(item, on_event)
    fake = Watching()
    client, store, bank, test, _ = make(None)
    attempt, _ = hand_in(client, bank, test, boards=2)
    attempt_id = attempt["id"]
    client.app.state.reviewer = fake
    client.get(f"/api/attempts/{attempt_id}", headers=auth(KID))
    assert [e["step"] for e in seen[0]["events"]] == ["boards", "question"] and seen[0]["events"][0]["count"] == 2
    assert seen[0]["events"][1] == {**seen[0]["events"][1], "n": 1, "i": 1, "of": 2} and seen[0]["questions"] == {}
    assert len(seen[2]["questions"]) == 1                                                  # the first question's review shows before the second
    assert seen[0]["state"] == "pending" and seen[0]["at"]
    assert seen[1]["events"][-1] == {**seen[1]["events"][-1], "step": "busy", "seconds": 8}
    assert store.get_attempt(attempt_id)["review"]["state"] == "done"


def test_gemini_says_when_it_waits_for_the_free_tier():
    steps = []
    reviewer = boardreview.GeminiReviewer("key", sleep=lambda s: None, gap=0)
    replies = [http_error(429, json.dumps({"error": {"details": [{"retryDelay": "7s"}]}}).encode()), answer({"verdict": "correct", "feedback": "f", "tip": "t"})]
    reviewer._call = lambda body: (lambda r: (_ for _ in ()).throw(r) if isinstance(r, Exception) else r)(replies.pop(0))
    reviewer.review_one(items()[0], on_event=lambda step, **info: steps.append((step, info)))
    assert steps == [("busy", {"seconds": 8}), ("resumed", {})]


def test_requests_keep_a_gap_for_the_free_tier_and_the_summary_has_no_picture():
    waits, sent, t = [], [], [100.0]
    reviewer = boardreview.GeminiReviewer("key", sleep=lambda s: (waits.append(round(s, 1)), t.__setitem__(0, t[0] + s)), gap=5.0, now=lambda: t[0])
    reviewer._call = lambda body: (sent.append(json.loads(body)), answer({"verdict": "correct", "feedback": "f", "tip": "t", "summary": "סיכום"}))[1]
    reviewer.review_one(items()[0])
    t[0] += 1.0
    reviewer.review_one(items()[0])
    assert reviewer.summarize([{"n": 1, "skill": "s", "verdict": "correct", "feedback": "f"}]) == "סיכום"
    assert waits == [4.0, 5.0] and not any("inline_data" in p for p in sent[2]["contents"][0]["parts"])


class QuotaAfterFirst(FakeReviewer):
    """The first question works, the second hits the quota (a stopping failure); with `fail` cleared everything works."""
    def __init__(self):
        super().__init__()
        self.quota = True

    def review_one(self, item, on_event=None):
        if self.quota and len(self.calls) == 1:
            self.calls.append(item)
            raise boardreview.ReviewFailure("rate_limited")
        return super().review_one(item)


def test_a_stopping_failure_keeps_what_was_checked_and_one_question_can_be_checked_alone():
    fake = QuotaAfterFirst()
    client, store, bank, test, _ = make(None)
    attempt, _ = hand_in(client, bank, test, boards=3)
    client.app.state.reviewer = fake
    view = client.get(f"/api/teaching/work/{attempt['id']}", headers=auth(TEACHER)).json()
    review = store.get_attempt(attempt["id"])["review"]
    assert review["state"] == "done" and len(review["questions"]) == 1 and review["missing"] == 2 and review["reason"] == "rate_limited"
    assert len(fake.calls) == 2 and view["ai"]["missing"] == 2                       # stopped: the third was never asked
    fake.quota = False
    third = attempt["questions"][2]["key"]
    got = client.post(f"/api/teaching/work/{attempt['id']}/review?key={third}", headers=auth(TEACHER)).json()
    review = store.get_attempt(attempt["id"])["review"]
    assert fake.calls[-1]["n"] == 3 and len(fake.calls) == 3 and set(review["questions"]) == {attempt["questions"][0]["key"], third}
    assert review["summary"] == got["ai"]["summary"] and next(q for q in got["questions"] if q["key"] == third)["ai"]
    no_board = attempt["questions"][5]["key"]
    assert client.post(f"/api/teaching/work/{attempt['id']}/review?key={no_board}", headers=auth(TEACHER)).status_code == 409
