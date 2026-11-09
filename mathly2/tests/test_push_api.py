"""Push notifications for photo requests (add-written-work 2.6), with a recording stand-in for the push service."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from mathly2 import clock, push
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.push import Gone, Pusher
from mathly2.store import InMemoryStore

TEACHER, KID, KID2 = "t@school.test", "kid@school.test", "kid2@school.test"
MON = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)
KEY_A, KEY_B = push.new_private_key(), push.new_private_key()


def uid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def sub(n, host="https://push.example/"):
    return {"endpoint": f"{host}{n}", "keys": {"p256dh": f"p{n}", "auth": f"a{n}"}}


class Recorder:
    """A stand-in for the push service: records what would be sent, and can answer 'gone' or fail for chosen endpoints."""

    def __init__(self):
        self.sent, self.gone, self.broken = [], set(), set()

    def __call__(self, subscription, payload, ttl):
        if subscription["endpoint"] in self.gone:
            raise Gone()
        if subscription["endpoint"] in self.broken:
            raise OSError("the network is down")
        self.sent.append((subscription["endpoint"], payload, ttl))


@pytest.fixture
def world(monkeypatch):
    bank = load_bank()
    lesson = next(u["id"] for u in bank.data["units"] if u.get("quiz"))
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=[lesson], teacher_email=TEACHER)
    for email in (KID, KID2):
        store.add_member(klass["id"], email)
    recorder = Recorder()
    pusher = Pusher(store, KEY_A, "mailto:dev@school.test", sender=recorder)
    client = TestClient(create_app(Settings(), bank=bank, store=store, pusher=pusher))
    moment = {"now": MON}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    client.set_time = lambda value: moment.update(now=value)
    client.store, client.recorder, client.pusher = store, recorder, pusher
    client.assignment = store.create_assignment(klass["id"], "דף", (MON + timedelta(days=7)).date(), TEACHER, "quiz", quiz_lesson=lesson)
    return client


def subscribe(client, n, who=KID, host="https://push.example/"):
    return client.post("/api/push/subscribe", json=sub(n, host), headers=auth(who))


def ask(client, who=KID):
    return client.post("/api/photo-requests", json={"assignment_id": client.assignment["id"], "device": "laptop"}, headers=auth(who))


def test_the_key_endpoint_gives_the_public_key_when_push_is_on(world):
    got = world.get("/api/push/key", headers=auth(KID))
    assert got.json() == {"enabled": True, "key": push.public_key(KEY_A)} and got.headers["cache-control"] == "no-store"
    assert world.get("/api/push/key").status_code == 401


def test_a_new_request_notifies_the_students_phones_with_the_requests_address_and_not_others(world):
    assert subscribe(world, 1).status_code == 200 and subscribe(world, 2).status_code == 200 and subscribe(world, 3, KID2).status_code == 200
    made = ask(world).json()
    sent = world.recorder.sent
    assert sorted(e for e, _, _ in sent) == ["https://push.example/1", "https://push.example/2"]                 # KID2's phone is not told
    payload, ttl = sent[0][1], sent[0][2]
    assert payload["url"] == f"/#/assignment/{world.assignment['id']}" and made["code"] in payload["body"] and payload["tag"] == f"photo-{world.assignment['id']}"
    assert payload["title"] and "דף" not in json.dumps(payload, ensure_ascii=False)                              # no assignment name on a locked screen
    assert ttl == 600                                                                                            # alive for the request's ten minutes


def test_a_computer_that_never_subscribed_gets_none_and_the_request_still_works(world):
    assert ask(world).status_code == 201 and world.recorder.sent == []


def test_a_subscription_the_push_service_no_longer_knows_is_deleted(world):
    subscribe(world, 1)
    subscribe(world, 2)
    world.recorder.gone.add("https://push.example/1")
    ask(world)
    assert [e for e, _, _ in world.recorder.sent] == ["https://push.example/2"]
    assert [s["endpoint"] for s in world.store.push_subscriptions_of(uid(KID))] == ["https://push.example/2"]


def test_a_failed_send_does_not_break_the_request_or_delete_the_subscription(world):
    subscribe(world, 1)
    world.recorder.broken.add("https://push.example/1")
    assert ask(world).status_code == 201
    assert len(world.store.push_subscriptions_of(uid(KID))) == 1


def test_changing_the_servers_key_drops_every_subscription(world):
    subscribe(world, 1)
    subscribe(world, 2, KID2)
    other_key = Pusher(world.store, KEY_B, "mailto:x@y.test", sender=world.recorder)
    assert other_key.key_id != world.pusher.key_id
    assert other_key.notify(uid(KID), {"title": "x"}, 60) == 0                                  # the old phones are dropped, none is told
    assert world.store.push_subscriptions_of(uid(KID)) == [] and world.store.push_subscriptions_of(uid(KID2)) == []
    other_key.subscribe(uid(KID), sub(9))                                                          # a phone turns notifications on again
    assert [s["endpoint"] for s in world.store.push_subscriptions_of(uid(KID))] == ["https://push.example/9"]
    assert world.store.push_subscriptions_of(uid(KID))[0]["key_id"] == other_key.key_id


def test_without_a_key_push_is_off_and_says_so_while_everything_else_works():
    bank = load_bank()
    lesson = next(u["id"] for u in bank.data["units"] if u.get("quiz"))
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=[lesson], teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    client = TestClient(create_app(Settings(), bank=bank, store=store))
    assert client.get("/api/push/key", headers=auth(KID)).json() == {"enabled": False, "key": ""}
    assert client.post("/api/push/subscribe", json=sub(1), headers=auth(KID)).status_code == 503
    row = store.create_assignment(klass["id"], "x", (MON + timedelta(days=7)).date(), TEACHER, "quiz", quiz_lesson=lesson)
    assert client.post("/api/photo-requests", json={"assignment_id": row["id"], "device": "d"}, headers=auth(KID)).status_code == 201


def test_a_key_that_is_not_a_key_turns_push_off_without_stopping_the_server():
    bad = Pusher(InMemoryStore(), "not-a-key", "mailto:x@y.test")
    assert bad.on is False and "valid" in bad.why and bad.public == ""
    assert Pusher(InMemoryStore(), "", "").on is False


@pytest.mark.parametrize("body", [{"endpoint": "http://insecure/1", "keys": {"p256dh": "p", "auth": "a"}}, {"endpoint": "https://x/1", "keys": {}},
                                  {"endpoint": "https://x/1", "keys": {"p256dh": "p"}}, {"endpoint": "https://x/1", "keys": {"p256dh": "p" * 300, "auth": "a"}}])
def test_a_subscription_that_is_not_one_is_refused(world, body):
    assert world.post("/api/push/subscribe", json=body, headers=auth(KID)).status_code == 400
    assert world.store.push_subscriptions_of(uid(KID)) == []


def test_the_same_phone_subscribing_again_keeps_one_row_and_unsubscribing_removes_only_mine(world):
    subscribe(world, 1)
    subscribe(world, 1)
    subscribe(world, 2, KID2)
    assert len(world.store.push_subscriptions_of(uid(KID))) == 1
    world.post("/api/push/unsubscribe", json={"endpoint": "https://push.example/2"}, headers=auth(KID))        # not KID's: nothing happens
    assert len(world.store.push_subscriptions_of(uid(KID2))) == 1
    world.post("/api/push/unsubscribe", json={"endpoint": "https://push.example/1"}, headers=auth(KID))
    assert world.store.push_subscriptions_of(uid(KID)) == []


def test_a_request_expiring_soon_has_a_short_lived_notification(world):
    subscribe(world, 1)
    world.set_time(MON)
    made = world.store.create_photo_request(uid(KID), world.assignment["id"], "laptop", "1234", MON, MON + timedelta(seconds=45))
    assert push.seconds_left(made, MON) == 45 and push.seconds_left(made, MON + timedelta(minutes=5)) == 0
    assert world.pusher.notify(uid(KID), {"t": 1}, 0) == 0                                              # a dead request is not worth a ring


def test_the_service_worker_is_served_from_the_root_and_the_manifest_is_linked(world):
    sw = world.get("/service-worker.js")
    assert sw.status_code == 200 and "javascript" in sw.headers["content-type"] and sw.headers["service-worker-allowed"] == "/" and sw.headers["cache-control"] == "no-cache"
    assert "addEventListener(\"push\"" in sw.text and "notificationclick" in sw.text
    manifest = world.get("/static/manifest.webmanifest").json()
    assert manifest["display"] == "standalone" and manifest["icons"] and manifest["dir"] == "rtl"
    assert 'rel="manifest"' in world.get("/").text


def test_the_real_sender_turns_a_404_or_410_into_gone_and_lets_other_errors_through(monkeypatch):
    import pywebpush

    class Response:
        def __init__(self, code):
            self.status_code = code

    def failing(code):
        def fake(*a, **k):
            raise pywebpush.WebPushException("push service said no", response=Response(code))
        return fake
    row = {"endpoint": "https://x/1", "p256dh": "p", "auth": "a"}
    for code in (404, 410):
        monkeypatch.setattr(pywebpush, "webpush", failing(code))
        with pytest.raises(Gone):
            push.web_push(row, {"t": 1}, KEY_A, "mailto:x@y.test", 60)
    monkeypatch.setattr(pywebpush, "webpush", failing(500))
    with pytest.raises(pywebpush.WebPushException):
        push.web_push(row, {"t": 1}, KEY_A, "mailto:x@y.test", 60)
    seen = {}
    monkeypatch.setattr(pywebpush, "webpush", lambda info, data, **kw: seen.update(info=info, data=data, **kw))
    push.web_push(row, {"title": "שלום"}, KEY_A, "mailto:x@y.test", 120)
    assert seen["ttl"] == 120 and seen["vapid_claims"] == {"sub": "mailto:x@y.test"} and "שלום" in seen["data"] and seen["info"]["keys"] == {"p256dh": "p", "auth": "a"}
