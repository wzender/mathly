import asyncio
import json
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

import httpx
import pytest

from app.auth import AuthUnavailable
from app.main import create_app
from scan_support import OTHER, OWNER, ScanAuth

MATH_JS = Path(__file__).resolve().parent.parent / "static" / "math.js"


class ProgressAuth(ScanAuth):
    """ScanAuth with an in-memory math_progress behind the PostgREST calls app/progress.py makes."""

    def __init__(self):
        self.rows: dict[str, dict] = {}

    def _admin(self, path, method="GET", body=None, prefer=""):
        table, _, query = path.partition("?")
        assert table == "/rest/v1/math_progress"
        q = dict(urllib.parse.parse_qsl(query))
        if method == "POST":
            assert "merge-duplicates" in prefer and q.get("on_conflict") == "user_id"
            self.rows[body["user_id"]] = dict(body)
            return None
        user = q["user_id"].removeprefix("eq.")
        return [{"data": self.rows[user]["data"]}] if user in self.rows else []


def client(app, user=None):
    headers = {"Authorization": f"Bearer {user}"} if user else {}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers)


def test_progress_is_kept_per_account():
    auth = ProgressAuth()
    app = create_app(auth=auth)

    async def check():
        async with client(app) as c:
            assert (await c.get("/api/math/progress")).status_code == 401
        async with client(app, OWNER) as owner, client(app, OTHER) as other:
            assert (await owner.get("/api/math/progress")).json() == {"progress": {}}
            mine = {"done": {"s1": "2026-11-01T10:00:00Z"}, "updated": 1}
            assert (await owner.put("/api/math/progress", json={"progress": mine})).json() == {"ok": True}
            assert (await owner.get("/api/math/progress")).json() == {"progress": mine}
            assert (await other.get("/api/math/progress")).json() == {"progress": {}}
            assert (await owner.put("/api/math/progress", json={"progress": [1]})).status_code == 400
            assert (await owner.put("/api/math/progress", content=b"not json")).status_code == 400
            big = {"progress": {"x": "a" * 1_000_001}}
            assert (await owner.put("/api/math/progress", json=big)).status_code == 413

    asyncio.run(check())


def test_missing_table_answers_503():
    class NoTable(ProgressAuth):
        def _admin(self, *a, **k):
            raise AuthUnavailable("supabase answered 404: relation math_progress does not exist")

    app = create_app(auth=NoTable())

    async def check():
        async with client(app, OWNER) as c:
            assert (await c.get("/api/math/progress")).status_code == 503
            assert (await c.put("/api/math/progress", json={"progress": {}})).status_code == 503

    asyncio.run(check())


def merge(a, b):
    """Run mergeProgress from static/math.js in Node."""
    source = MATH_JS.read_text(encoding="utf-8")
    fn = re.search(r"const isObj=.*?\n(function mergeProgress\(a,b\)\{.*?\n\})", source, re.S)
    script = fn.group(0) + f"\nprocess.stdout.write(JSON.stringify(mergeProgress({json.dumps(a)},{json.dumps(b)})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_merge_keeps_the_work_of_both_devices():
    phone = {"updated": 200, "done": {"a": "2026-11-02", "b": "2026-11-02"}, "gold": {"b": "2026-11-02"},
             "solved": {"c": [0, 2]}, "tries": {"c": 3}, "days": {"2026-11-02": 4}, "comets": ["pi"],
             "slips": [{"at": "2026-11-02T09:00", "id": "c", "q": 1, "m": "sign"}],
             "at": {"c": 2}, "run": {"c": 1}, "seen": {"a": "2026-11-02"}, "cometDay": "2026-11-02"}
    laptop = {"updated": 100, "done": {"a": "2026-11-01", "d": "2026-11-01"}, "solved": {"c": [1]},
              "tries": {"c": 5}, "days": {"2026-11-01": 2, "2026-11-02": 1}, "comets": ["pi", "e"],
              "slips": [{"at": "2026-11-01T09:00", "id": "c", "q": 0, "m": "sign"}],
              "at": {"c": 1, "d": 0}, "run": {"c": 4}, "seen": {"a": "2026-11-03"},
              "quizzes": [{"at": "2026-11-01T08:00", "n": 5}]}
    for out in (merge(phone, laptop), merge(laptop, phone)):
        assert out["done"] == {"a": "2026-11-01", "b": "2026-11-02", "d": "2026-11-01"}
        assert out["gold"] == {"b": "2026-11-02"}
        assert out["solved"] == {"c": [0, 1, 2]}
        assert out["tries"] == {"c": 5}
        assert out["days"] == {"2026-11-01": 2, "2026-11-02": 4}
        assert sorted(out["comets"]) == ["e", "pi"]
        assert [s["at"] for s in out["slips"]] == ["2026-11-01T09:00", "2026-11-02T09:00"]
        assert out["at"] == {"c": 2, "d": 0} and out["run"] == {"c": 1}   # where the student is: the newer copy
        assert out["seen"] == {"a": "2026-11-03"} and out["cometDay"] == "2026-11-02"
        assert out["quizzes"] == [{"at": "2026-11-01T08:00", "n": 5}] and out["updated"] == 200
    alone = merge({}, phone)   # a device with nothing yet takes the server's copy as it is
    assert alone == merge(phone, {}) and {k: alone[k] for k in phone} == phone


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_merge_keeps_the_most_worked_example_openings_and_the_latest_time():
    phone = {"updated": 200, "examples": {"a": {"n": 2, "last": "2026-11-02T10:00:00Z"}}}
    laptop = {"updated": 100, "examples": {"a": {"n": 3, "last": "2026-11-01T10:00:00Z"}, "b": {"n": 1, "last": "2026-11-01T11:00:00Z"}}}
    for out in (merge(phone, laptop), merge(laptop, phone)):
        assert out["examples"] == {"a": {"n": 3, "last": "2026-11-02T10:00:00Z"}, "b": {"n": 1, "last": "2026-11-01T11:00:00Z"}}
    assert merge({}, phone)["examples"] == phone["examples"]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_merge_keeps_the_most_wrong_answers_per_skill():
    phone = {"updated": 200, "wrongs": {"a": 2, "b": 1}}
    laptop = {"updated": 100, "wrongs": {"a": 5}}
    for out in (merge(phone, laptop), merge(laptop, phone)):
        assert out["wrongs"] == {"a": 5, "b": 1}
