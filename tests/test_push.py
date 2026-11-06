import asyncio
import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app import push as pushes
from app.answer_scans import scan_code
from app.auth import AuthUnavailable
from app.main import create_app
from scan_support import OTHER, OWNER, ScanAuth, answer_store, postgres_server  # noqa: F401

KEY = pushes.new_private_key()
SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "p" * 87, "auth": "a" * 22}}


class PushAuth(ScanAuth):
    """ScanAuth with an in-memory math_push_subs behind the PostgREST calls Push makes."""

    def __init__(self):
        self.rows: dict[str, dict] = {}

    def _admin(self, path, method="GET", body=None, prefer=""):
        table, _, query = path.partition("?")
        if table != "/rest/v1/math_push_subs":
            return super()._admin(path)   # no other tables here (a quiz answer looks for a final sitting)
        q = dict(urllib.parse.parse_qsl(query))
        match = lambda r: all(r[k] == v.removeprefix("eq.") for k, v in q.items() if k in ("endpoint", "user_id"))
        if method == "POST":
            self.rows[body["endpoint"]] = dict(body)
            return None
        if method == "DELETE":
            for e in [e for e, r in self.rows.items() if match(r)]:
                del self.rows[e]
            return None
        return [r for r in self.rows.values() if match(r)]


def scan(state="waiting", minutes=10, sid="7d9c2f0e-3c1a-4c55-9a1e-2b3c4d5e6f70"):
    end = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return {"attempt": {"id": "11111111-1111-1111-1111-111111111111"},
            "scan": {"id": sid, "state": state, "expires_at": end.isoformat()}}


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def webpush(sub, data, **kwargs):
        calls.append({"endpoint": sub["endpoint"], "data": json.loads(data), **kwargs})

    import pywebpush
    monkeypatch.setattr(pywebpush, "webpush", webpush)
    return calls


def test_payload_has_code_and_no_question_and_replaces_by_attempt():
    result = scan()
    msg = pushes.scan_payload(result)
    assert scan_code(result["scan"]["id"]) in msg["body"]
    assert msg["tag"] == "scan-11111111-1111-1111-1111-111111111111"
    assert msg["url"] == "/?from=push-scan"
    assert 590 <= pushes.seconds_left(result) <= 600
    assert pushes.seconds_left(scan(minutes=-1)) == 0
    assert pushes.seconds_left({"scan": {"expires_at": None}}) == 900


def test_keys_round_trip_and_off_reasons():
    assert len(pushes.public_key(KEY)) == 87   # 65 bytes, base64url
    assert pushes.Push(PushAuth(), "").why == "VAPID_PRIVATE_KEY is not set"
    assert pushes.Push(PushAuth(), "not a key!").why == "VAPID_PRIVATE_KEY is not a valid key"
    p = pushes.Push(PushAuth(), KEY, "mailto:a@test.invalid")
    assert p.on and p.public == pushes.public_key(KEY)


def test_request_goes_once_to_the_accounts_phones_and_gone_ones_are_deleted(sent, monkeypatch):
    auth = PushAuth()
    p = pushes.Push(auth, KEY, "mailto:a@test.invalid")
    p.save(OWNER, SUB)
    p.save(OWNER, {**SUB, "endpoint": "https://push.example/gone"})
    p.save(OTHER, {**SUB, "endpoint": "https://push.example/other"})
    with pytest.raises(ValueError):
        p.save(OWNER, {"endpoint": "http://insecure", "keys": SUB["keys"]})

    import pywebpush
    real = pywebpush.webpush

    def webpush(sub, data, **kwargs):
        if sub["endpoint"].endswith("/gone"):
            raise pywebpush.WebPushException("gone", response=type("R", (), {"status_code": 410})())
        return real(sub, data, **kwargs)

    monkeypatch.setattr(pywebpush, "webpush", webpush)
    assert p.scan_requested(OWNER, scan()) == 1
    assert [c["endpoint"] for c in sent] == [SUB["endpoint"]]
    assert sent[0]["headers"] == {"Urgency": "high"} and 0 < sent[0]["ttl"] <= 600
    assert "https://push.example/gone" not in auth.rows and "https://push.example/other" in auth.rows
    assert p.scan_requested(OWNER, scan()) == 0   # the same request again: no second ring
    assert p.scan_requested(OWNER, scan("received", sid="22222222-2222-2222-2222-222222222222")) == 0
    assert p.scan_requested(OWNER, scan(minutes=-1, sid="33333333-3333-3333-3333-333333333333")) == 0
    assert len(sent) == 1


def test_missing_table_does_not_break_the_request(sent):
    class NoTable(PushAuth):
        def _admin(self, *a, **k):
            raise AuthUnavailable("supabase answered 404: relation math_push_subs does not exist")

    assert pushes.Push(NoTable(), KEY, "mailto:a@test.invalid").scan_requested(OWNER, scan()) == 0


def test_subscribe_api_moves_a_phone_between_accounts(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", KEY)
    auth = PushAuth()
    app = create_app(auth=auth)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get("/api/push")).status_code == 401
            owner, other = ({"Authorization": f"Bearer {u}"} for u in (OWNER, OTHER))
            assert (await c.get("/api/push", headers=owner)).json()["key"] == pushes.public_key(KEY)
            assert (await c.post("/api/push/subscribe", json={"endpoint": "x"}, headers=owner)).status_code == 400
            assert (await c.post("/api/push/subscribe", json=SUB, headers=owner)).json() == {"ok": True}
            assert auth.rows[SUB["endpoint"]]["user_id"] == OWNER
            assert (await c.post("/api/push/subscribe", json=SUB, headers=other)).status_code == 200
            assert auth.rows[SUB["endpoint"]]["user_id"] == OTHER   # one row per phone: the account signed in now
            await c.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]}, headers=owner)
            assert SUB["endpoint"] in auth.rows   # another account cannot remove it
            await c.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]}, headers=other)
            assert not auth.rows
            sw = await c.get("/service-worker.js")
            assert "showNotification" in sw.text and 'addEventListener("fetch"' not in sw.text and sw.headers["cache-control"] == "no-store"

    asyncio.run(check())


def test_push_off_without_key(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    app = create_app(auth=PushAuth())

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"Authorization": f"Bearer {OWNER}"}) as c:
            assert (await c.get("/api/push")).json() == {"key": ""}
            assert (await c.post("/api/push/subscribe", json=SUB)).status_code == 503

    asyncio.run(check())


def test_computer_request_pushes_to_the_phone(answer_store, sent, monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", KEY)
    auth = PushAuth()
    app = create_app(auth=auth)
    app.state.answers = answer_store
    app.state.push.save(OWNER, SUB)
    aid = answer_store.action(OWNER, "resume", question_id="q", question_version="v1",
                              snapshot={"question": "Prove it", "type": "open-ended"})["attempt"]["id"]

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"Authorization": f"Bearer {OWNER}"}) as c:
            first = (await c.post(f"/api/math/answer-attempts/{aid}/scans", json={})).json()
            again = (await c.post(f"/api/math/answer-attempts/{aid}/scans", json={})).json()
            assert again["scan"]["id"] == first["scan"]["id"]
            renewed = (await c.post(f"/api/math/answer-attempts/{aid}/scans", json={"renew": True})).json()
            return first, renewed

    first, renewed = asyncio.run(check())
    assert len(sent) == 2   # the repeated request did not ring again; the renewed one did
    assert first["scan"]["code"] in sent[0]["data"]["body"] and renewed["scan"]["code"] in sent[1]["data"]["body"]
    assert sent[0]["data"]["tag"] == sent[1]["data"]["tag"] == f"scan-{aid}"
    assert "Prove it" not in json.dumps(sent)


def test_migration_keeps_subscriptions_from_browsers(postgres_server):
    import uuid

    import psycopg
    database = "push_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute("create database " + database)
    try:
        with psycopg.connect(postgres_server.get_uri(database=database), autocommit=True) as c:
            c.execute("create schema auth; create table auth.users(id uuid primary key);"
                      "grant usage on schema public to anon, authenticated, service_role;")
            c.execute(Path("supabase/migrations/20261103180000_math_push_subs.sql").read_text())
            c.execute("insert into auth.users values(%s)", (OWNER,))
            c.execute("set role service_role")
            c.execute("insert into math_push_subs(endpoint,user_id,p256dh,auth) values(%s,%s,'p','a')", (SUB["endpoint"], OWNER))
            c.execute("reset role; set role authenticated")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute("select * from math_push_subs")
            c.execute("reset role")
            with pytest.raises(psycopg.errors.CheckViolation):
                c.execute("insert into math_push_subs(endpoint,user_id,p256dh,auth) values('http://x',%s,'p','a')", (OWNER,))
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute("drop database " + database + " with (force)")


def test_a_devices_own_upload_rings_no_phone_and_is_offered_to_none(answer_store, sent, monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", KEY)
    app = create_app(auth=PushAuth())
    app.state.answers = answer_store
    app.state.push.save(OWNER, SUB)
    own = answer_store.action(OWNER, "resume", question_id="quiz:t:0", question_version="v1",
                              snapshot={"question": "Solve", "type": "open-ended"})["attempt"]["id"]
    asked = answer_store.action(OWNER, "resume", question_id="quiz:t:1", question_version="v1",
                                snapshot={"question": "Prove", "type": "open-ended"})["attempt"]["id"]

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"Authorization": f"Bearer {OWNER}"}) as c:
            direct = (await c.post(f"/api/math/answer-attempts/{own}/scans", json={"renew": True, "direct": True})).json()
            phone = (await c.post(f"/api/math/answer-attempts/{asked}/scans", json={"renew": True})).json()
            listed = (await c.get("/api/math/answer-scans")).json()
            return direct, phone, listed

    direct, phone, listed = asyncio.run(check())
    assert len(sent) == 1 and phone["scan"]["code"] in sent[0]["data"]["body"]   # only the request for the phone rang
    assert [r["scan"]["id"] for r in listed] == [phone["scan"]["id"]]   # and only it waits for a phone
    assert direct["scan"]["state"] == "waiting"   # the device's own request works as before
