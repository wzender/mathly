"""Slow-changing facts are remembered (cache-and-instant-screens 1.2): with every store call made to wait, the second opening is quicker,
and a change shows at once."""
import time
from datetime import timedelta

from fastapi.testclient import TestClient

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.cached import CachedStore
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.tests.test_database_waits import DELAY, SlowStore

TEACHER = "t@school.test"
H = {"Authorization": f"Bearer dev:{TEACHER}"}


def test_second_opening_is_quicker_and_a_change_shows_at_once():
    bank = load_bank()
    slow = SlowStore()
    lessons = [l["id"] for l in bank.lessons][:3]
    klass = slow.create_class("setup", "A", lessons=lessons, teacher_email=TEACHER)
    slow.add_member(klass["id"], "kid@school.test")
    cached = CachedStore(slow, 30)
    client = TestClient(create_app(Settings(), bank=bank, store=cached))
    client.get("/api/me", headers=H)
    slow.slow = True

    def took(path):
        start = time.perf_counter()
        r = client.get(path, headers=H)
        assert r.status_code == 200, r.text
        return time.perf_counter() - start, r.json()

    for path in ("/api/teaching/counts", "/api/teaching/assignments", "/api/teaching/tests"):
        cached.forget()
        first, _ = took(path)
        second, _ = took(path)
        assert second < first - DELAY / 2, (path, first, second)

    _, before = took("/api/teaching/assignments")
    assert before[0]["assignments"] == []
    r = client.post(f"/api/classes/{klass['id']}/assignments", headers=H,
                    json={"title": "חדש", "kind": "quiz", "quiz_lesson": lessons[0], "due_date": str(clock.school_day() + timedelta(days=5))})
    assert r.status_code in (200, 201), r.text
    _, after = took("/api/teaching/assignments")
    assert len(after[0]["assignments"]) == 1
