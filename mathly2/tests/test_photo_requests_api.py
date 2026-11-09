"""The photo request: a computer asks the student's phone for a photo (add-written-work 2.5)."""
import io
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

TEACHER, KID, KID2, OUTSIDER = "t@school.test", "kid@school.test", "kid2@school.test", "out@school.test"
MON = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)
MIN = timedelta(minutes=1)


def uid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def jpeg():
    out = io.BytesIO()
    Image.new("RGB", (80, 50), "green").save(out, "JPEG")
    return out.getvalue()


@pytest.fixture
def world(monkeypatch):
    bank = load_bank()
    lesson = next(u["id"] for u in bank.data["units"] if u.get("quiz"))
    store = InMemoryStore()
    a = store.create_class("setup", "A", lessons=[lesson], teacher_email=TEACHER)
    b = store.create_class("setup", "B", lessons=[lesson], teacher_email="t2@school.test")
    for email in (KID, KID2):
        store.add_member(a["id"], email)
    store.add_member(b["id"], OUTSIDER)
    client = TestClient(create_app(Settings(), bank=bank, store=store))
    moment = {"now": MON}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    client.set_time = lambda value: moment.update(now=value)
    due = (MON + timedelta(days=7)).date()
    client.store, client.assignment = store, store.create_assignment(a["id"], "דף", due, TEACHER, "quiz", quiz_lesson=lesson)
    client.other = store.create_assignment(b["id"], "אחר", due, "t2@school.test", "quiz", quiz_lesson=lesson)
    client.exam = store.create_assignment(a["id"], "תרגול", due, TEACHER, "exercise_test", test_id=1, exercise_number=1)
    return client


def ask(client, who=KID, device="laptop", assignment=None):
    return client.post("/api/photo-requests", json={"assignment_id": (assignment or client.assignment)["id"], "device": device}, headers=auth(who))


def phone_list(client, who=KID, device="phone"):
    return client.get("/api/photo-requests/open", params={"device": device}, headers=auth(who)).json()


def test_a_request_has_a_four_digit_code_ten_minutes_and_starts_waiting(world):
    got = ask(world)
    assert got.status_code == 201
    body = got.json()
    assert re.fullmatch(r"\d{4}", body["code"]) and body["state"] == "waiting" and body["picture_id"] is None and body["assignment_id"] == world.assignment["id"]
    assert datetime.fromisoformat(body["expires_at"]) == MON + 10 * MIN


def test_the_same_code_is_on_the_computer_and_the_phone(world):
    world.app.state.photo_code = lambda: 42
    code = ask(world).json()["code"]
    assert code == "0042"                                             # zero padded
    on_phone = phone_list(world)
    assert len(on_phone) == 1 and on_phone[0]["code"] == code and on_phone[0]["assignment"]["title"] == "דף"


def test_the_phone_does_not_show_the_request_its_own_device_made_and_others_do(world):
    ask(world, device="laptop")
    assert phone_list(world, device="laptop") == []                   # the computer that asked is not asked to photograph
    assert len(phone_list(world, device="phone")) == 1
    assert phone_list(world, KID2) == []                              # another student's phone sees nothing


def test_a_newer_request_for_the_same_answer_replaces_the_older(world):
    first = ask(world).json()
    second = ask(world).json()
    assert world.get(f"/api/photo-requests/{first['id']}", headers=auth(KID)).json()["state"] == "superseded"
    assert world.get(f"/api/photo-requests/{second['id']}", headers=auth(KID)).json()["state"] == "waiting"
    assert [r["id"] for r in phone_list(world)] == [second["id"]]
    late = world.post(f"/api/photo-requests/{first['id']}/picture", content=jpeg(), headers={**auth(KID), "Content-Type": "image/jpeg"})
    assert late.status_code == 409 and "הוחלפה" in late.json()["detail"]


def test_a_request_expires_after_ten_minutes_by_the_servers_clock(world):
    made = ask(world).json()
    world.set_time(MON + 9 * MIN)
    assert world.get(f"/api/photo-requests/{made['id']}", headers=auth(KID)).json()["state"] == "waiting"
    world.set_time(MON + 10 * MIN)
    assert world.get(f"/api/photo-requests/{made['id']}", headers=auth(KID)).json()["state"] == "expired"
    assert phone_list(world) == []
    upload = world.post(f"/api/photo-requests/{made['id']}/picture", content=jpeg(), headers={**auth(KID), "Content-Type": "image/jpeg"})
    assert upload.status_code == 409 and "פגה" in upload.json()["detail"] and world.store.pictures() == []
    assert world.post(f"/api/photo-requests/{made['id']}/start", headers=auth(KID)).status_code == 409


def test_the_states_go_waiting_uploading_received_with_the_picture(world):
    made = ask(world).json()
    started = world.post(f"/api/photo-requests/{made['id']}/start", headers=auth(KID))
    assert started.status_code == 200 and started.json()["state"] == "uploading"
    assert world.get(f"/api/photo-requests/{made['id']}", headers=auth(KID)).json()["state"] == "uploading" and len(phone_list(world)) == 1
    done = world.post(f"/api/photo-requests/{made['id']}/picture", content=jpeg(), headers={**auth(KID), "Content-Type": "image/jpeg"})
    assert done.status_code == 200 and done.json()["state"] == "received"
    pic = world.store.get_picture(done.json()["picture_id"])
    assert pic["kind"] == "answer" and pic["owner_id"] == uid(KID)
    assert world.get(f"/api/photo-requests/{made['id']}", headers=auth(KID)).json()["picture_id"] == pic["id"] and phone_list(world) == []
    assert world.get(f"/api/pictures/{pic['id']}", headers=auth(KID)).status_code == 200            # the computer can read it to add it to the answer
    again = world.post(f"/api/photo-requests/{made['id']}/picture", content=jpeg(), headers={**auth(KID), "Content-Type": "image/jpeg"})
    assert again.status_code == 409                                                                  # one picture per request


def test_a_bad_upload_makes_the_request_failed_and_stores_nothing(world):
    made = ask(world).json()
    bad = world.post(f"/api/photo-requests/{made['id']}/picture", content=b"not an image", headers={**auth(KID), "Content-Type": "image/jpeg"})
    assert bad.status_code == 400
    assert world.get(f"/api/photo-requests/{made['id']}", headers=auth(KID)).json()["state"] == "failed" and world.store.pictures() == []
    assert phone_list(world) == []


def test_another_student_cannot_read_or_answer_a_request_and_only_class_assignments_work(world):
    made = ask(world).json()
    for call in (lambda: world.get(f"/api/photo-requests/{made['id']}", headers=auth(KID2)),
                 lambda: world.post(f"/api/photo-requests/{made['id']}/start", headers=auth(KID2)),
                 lambda: world.post(f"/api/photo-requests/{made['id']}/picture", content=jpeg(), headers={**auth(KID2), "Content-Type": "image/jpeg"})):
        assert call().status_code == 404
    assert ask(world, assignment=world.other).status_code == 404                                    # an assignment of another class
    assert ask(world, assignment=world.exam).status_code == 422                                     # an exercise test is not handed in as a picture
    assert world.get("/api/photo-requests/nope", headers=auth(KID)).status_code == 404
    assert world.post("/api/photo-requests", json={"assignment_id": world.assignment["id"], "device": "x"}).status_code == 401
