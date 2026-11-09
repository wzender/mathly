"""The AI core (add-ai-help 1.2): failure reasons, cost, fail-closed checks, no name or email in a payload."""
import json

import pytest

from mathly2 import ai


def test_each_failure_reason_is_told_apart_and_has_what_to_do():
    anthropic = pytest.importorskip("anthropic")
    import httpx
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def status(cls, code, message=""):
        return cls(message, response=httpx.Response(code, request=req, json={"error": {"message": message}}), body={"error": {"message": message}})
    cases = [(status(anthropic.AuthenticationError, 401), "api_key_invalid"), (status(anthropic.PermissionDeniedError, 403), "permission"),
             (status(anthropic.NotFoundError, 404), "model_not_found"), (status(anthropic.RateLimitError, 429), "rate_limited"),
             (status(anthropic.BadRequestError, 400, "Your credit balance is too low"), "no_credit"),
             (status(anthropic.APIStatusError, 529, "Overloaded"), "overloaded"), (status(anthropic.BadRequestError, 400, "bad"), "bad_request"),
             (status(anthropic.InternalServerError, 500, "boom"), "provider_error"), (anthropic.APIConnectionError(request=req), "no_connection")]
    for exc, want in cases:
        reason, detail = ai.failure_reason(exc)
        assert reason == want and detail and reason in ai.FAILURES and all(ai.FAILURES[reason]), (want, reason)
    assert set(ai.FAILURES) >= {"api_key_missing", "refused", "incomplete", "bad_output"}


def test_cost_uses_the_longest_model_prefix_and_an_unknown_model_is_priced_as_the_default():
    usage = {"model": "claude-opus-5-5-20261101", "input_tokens": 1_000_000, "output_tokens": 1_000_000, "cache_read_tokens": 1_000_000, "cache_write_tokens": 1_000_000}
    assert ai.cost(usage) == round(4.00 + 20.00 + 0.20 + 4.00 * 1.25, 6)
    assert ai.cost({**usage, "model": "claude-sonnet-5-5"}) == round(2.00 + 10.00 + 0.20 + 2.00 * 1.25, 6)
    assert ai.cost({**usage, "model": "something-new"}) == ai.cost(usage)
    row = ai.usage_row({"model": "claude-opus-5-5", "input_tokens": 10, "output_tokens": 5}, "photo", "r1", "u1")
    assert row["feature"] == "photo" and row["request_id"] == "r1" and row["cost_usd"] > 0


GOOD = {"readable": True, "confident": True, "answer_correct": True, "reasoning_correct": True, "drawing_correct": True, "units_correct": True,
        "complete": True, "transcription": "x=2", "feedback": "יפה", "next_step": "", "solution": "x=2", "score": 100}


def test_a_check_fails_closed():
    assert ai.validate_check(GOOD)["verdict"] == "correct" and ai.validate_check(GOOD)["score"] == 100
    assert ai.validate_check({**GOOD, "readable": False})["score"] is None and ai.validate_check({**GOOD, "readable": False})["verdict"] == "unreadable"
    assert ai.validate_check({**GOOD, "confident": False})["score"] is None and ai.validate_check({**GOOD, "confident": False})["verdict"] == "needs_review"
    inconsistent = ai.validate_check({**GOOD, "answer_correct": False})                       # a score of 100 with a wrong answer never stands
    assert inconsistent["score"] == 99 and inconsistent["verdict"] == "partial"
    assert ai.validate_check({**GOOD, "score": 0, "answer_correct": False})["verdict"] == "incorrect"
    for broken in ({**GOOD, "score": 101}, {**GOOD, "score": "100"}, {**GOOD, "feedback": " "}, {**GOOD, "transcription": ""}, {**GOOD, "readable": "yes"},
                   {k: v for k, v in GOOD.items() if k != "score"}, {**GOOD, "extra": 1}, "nope"):
        with pytest.raises(ai.AIFailure) as caught:
            ai.validate_check(broken)
        assert caught.value.reason == "bad_output"


def test_the_fake_and_the_missing_key_behave():
    fake = ai.FakeAI()
    out = fake.solve(b"img", "image/jpeg", [{"id": "s1", "name": "n"}])
    assert out["steps"][0]["hint"] and out["skill"] == "s1" and fake.calls[0][0] == "solve"
    with pytest.raises(ai.AIFailure) as missing:
        ai.MissingAI().check([], {})
    assert missing.value.reason == "api_key_missing"
    with pytest.raises(ai.AIFailure) as failed:
        ai.FakeAI(fail="no_credit").solve(b"", "image/jpeg", [])
    assert failed.value.reason == "no_credit"


def test_the_prompts_and_the_payload_hold_no_name_or_email():
    snapshot = {"title": "משימה", "note": "פתרו", "questions": [{"question": "$x+1=3$", "points": 25}]}
    fake = ai.FakeAI()
    fake.check([("תשובת התלמיד", b"jpeg")], snapshot)
    sent = json.dumps(fake.calls[0][2], ensure_ascii=False)
    assert "@" not in sent and "email" not in sent and "name" not in sent
    assert "@" not in ai.CHECK_PROMPT and "@" not in ai.photo_prompt([{"id": "a", "name": "n"}])
