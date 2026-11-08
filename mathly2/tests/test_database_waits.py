"""Few database round trips (fewer-database-calls 1.1): with every store call made to wait, a screen and an answer must still be quick,
because independent reads run at the same time and repeated reads happen once."""
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

DELAY = 0.1
KID = "kid@school.test"
H = {"Authorization": f"Bearer dev:{KID}"}


class SlowStore(InMemoryStore):
    """Every public call takes DELAY seconds, like a remote database."""
    slow = False

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if callable(attr) and not name.startswith("_") and name != "calls" and super().__getattribute__("slow"):
            def waiting(*a, **k):
                time.sleep(DELAY)
                return attr(*a, **k)
            return waiting
        return attr


@pytest.fixture(scope="module")
def world():
    bank = load_bank()
    store = SlowStore()
    lessons = [l["id"] for l in bank.lessons][:6]
    klass = store.create_class("setup", "A", lessons=lessons, teacher_email="t@school.test")
    store.add_member(klass["id"], KID)
    from datetime import timedelta
    from mathly2 import clock
    store.create_test(klass["id"], clock.school_day() + timedelta(days=9), lessons[:2], "t@school.test", created_at=clock.now() - timedelta(days=20))
    client = TestClient(create_app(Settings(), bank=bank, store=store))
    skill = next(s["id"] for s in bank.skills if s["unit"] in lessons and bank.question_keys(s["id"]))
    client.get("/api/me", headers=H)                               # warm the roles cache, as a signed-in student's later requests are
    client.get(f"/api/skills/{skill}", headers=H)                  # the question is chosen and remembered on the first open
    store.slow = True
    yield client, bank, skill, store
    store.slow = False


def timed(client, method, path, **kw):
    start = time.perf_counter()
    response = client.request(method, path, headers=H, **kw)
    assert response.status_code == 200, response.text
    return time.perf_counter() - start


@pytest.mark.parametrize("path", ["/api/home", "/api/path", "/api/grades", "/api/collection"])
def test_a_screen_waits_for_the_database_at_most_three_times_in_a_row(world, path):
    client, _, _, _ = world
    assert timed(client, "GET", path) < 0.55


def test_opening_a_skill_waits_at_most_three_times_in_a_row(world):
    client, _, skill, _ = world
    assert timed(client, "GET", f"/api/skills/{skill}") < 0.55


def test_an_answer_waits_at_most_four_times_in_a_row(world):
    client, bank, skill, store = world
    store.slow = False
    key = client.get(f"/api/skills/{skill}", headers=H).json()["question"]["key"]
    store.slow = True
    assert timed(client, "POST", f"/api/skills/{skill}/answer", json={"question_key": key, "choice": 0}) < 0.75


def test_me_waits_at_most_two_or_three_times(world):
    client, _, _, _ = world
    assert timed(client, "GET", "/api/me") < 0.55
