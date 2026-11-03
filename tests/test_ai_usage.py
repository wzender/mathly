import asyncio
from types import SimpleNamespace

import httpx

from app import ai_usage
from app.auth import AuthUnavailable
from app.main import create_app


class FakeStore:
    secret = "secret"

    def __init__(self, rows=None, fail=None):
        self.rows, self.fail, self.saved = rows or [], fail, []

    def _admin(self, path, method="GET", body=None, prefer=""):
        if self.fail:
            raise self.fail
        if method == "POST":
            self.saved.append((path, body))
            return None
        return self.rows


def drain():
    ai_usage._pool.submit(lambda: None).result(timeout=5)


def test_cost_uses_the_model_prices():
    usage = {"model": "claude-opus-5-5", "input_tokens": 1_000_000, "output_tokens": 1_000_000,
             "cache_read_tokens": 1_000_000, "cache_write_tokens": 1_000_000}
    assert ai_usage.cost(usage) == 4 + 20 + 0.20 + 5
    assert ai_usage.cost({**usage, "model": "claude-opus-5"}) == 5 + 25 + 0.5 + 6.25   # not the 5.5 price
    assert ai_usage.cost({"model": "claude-haiku-5-5", "output_tokens": 2_000_000}) == 1.0


def test_usage_of_reads_a_response_and_tolerates_fakes():
    res = SimpleNamespace(model="claude-opus-5-5", usage=SimpleNamespace(
        input_tokens=10, output_tokens=20, cache_read_input_tokens=None, cache_creation_input_tokens=5))
    assert ai_usage.usage_of(res) == {"model": "claude-opus-5-5", "input_tokens": 10, "output_tokens": 20,
                                      "cache_read_tokens": 0, "cache_write_tokens": 5}
    assert ai_usage.usage_of(SimpleNamespace(model="x")) is None


def test_record_saves_a_row_and_never_raises():
    store = FakeStore()
    usage = {"model": "claude-opus-5-5", "input_tokens": 1000, "output_tokens": 500,
             "cache_read_tokens": 0, "cache_write_tokens": 0}
    ai_usage.record(store, "u1", "photo", usage)
    drain()
    [(path, row)] = store.saved
    assert path == ai_usage.TABLE and row["feature"] == "photo" and row["user_id"] == "u1"
    assert row["cost_usd"] == round((1000 * 4 + 500 * 20) / 1e6, 6)
    ai_usage.record(FakeStore(fail=AuthUnavailable("supabase answered 404: missing")), None, "grading", usage)
    ai_usage.record(FakeStore(fail=RuntimeError("boom")), None, "grading", usage)
    drain()
    ai_usage.record(None, "u1", "photo", usage)       # no database
    ai_usage.record(store, "u1", "photo", None)       # no usage
    drain()
    assert len(store.saved) == 1


def test_summary_totals_per_feature_and_model():
    today = "2999-01-01"
    rows = [{"created_at": f"{today}T10:00:00+00:00", "feature": "photo", "model": "claude-opus-5-5",
             "input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 10, "cache_write_tokens": 0, "cost_usd": "0.5"},
            {"created_at": "2000-01-01T10:00:00+00:00", "feature": "grading", "model": "claude-opus-5-5",
             "input_tokens": 200, "output_tokens": 100, "cache_read_tokens": 0, "cache_write_tokens": 0, "cost_usd": 0.25}]
    out = ai_usage.summary(FakeStore(rows))
    assert out["total"] == {"calls": 2, "input_tokens": 300, "output_tokens": 150, "cache_tokens": 10, "cost_usd": 0.75}
    assert out["by_feature"]["photo"]["cost_usd"] == 0.5 and out["by_feature"]["grading"]["calls"] == 1
    assert out["by_model"]["claude-opus-5-5"]["calls"] == 2


def test_the_photo_route_records_usage_and_does_not_return_it(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    recorded = []
    monkeypatch.setattr(ai_usage, "record", lambda auth, user_id, feature, usage: recorded.append((feature, usage)))

    class Solver:
        def solve(self, image, media_type):
            return {"readable": True, "problem": "p", "steps": [], "answer": "a", "skill": "", "note": "",
                    "usage": {"model": "claude-opus-5-5", "input_tokens": 1, "output_tokens": 2,
                              "cache_read_tokens": 0, "cache_write_tokens": 0}}

    app = create_app()
    app.state.photo, app.state.photo_key = Solver(), "test"

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/math/photo", files={"photo": ("p.jpg", b"jpeg", "image/jpeg")})
            assert response.status_code == 200 and "usage" not in response.json()
    asyncio.run(check())
    assert recorded == [("photo", {"model": "claude-opus-5-5", "input_tokens": 1, "output_tokens": 2,
                                   "cache_read_tokens": 0, "cache_write_tokens": 0})]
