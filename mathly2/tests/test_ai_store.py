"""The AI tables through both stores (add-ai-help 1.1): the in-memory rules, and what the Supabase store would send."""
from datetime import date, datetime, timezone

import pytest

from mathly2.store import InMemoryStore
from mathly2.tests.test_store import Recorder

NOW = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)
U = "11111111-1111-1111-1111-111111111111"
DAY = date(2026, 11, 9)


def row(**extra):
    base = {"id": "r1", "kind": "photo", "user_id": U, "class_id": 1, "state": "waiting", "picture_id": "p1", "assignment_id": None, "skill_id": None,
            "snapshot": None, "result": None, "teacher_note": "", "failure": None, "budget": None, "sent_by": None,
            "created_at": "2026-11-09T09:00:00+00:00", "sent_at": None, "done_at": None}
    return {**base, **extra}


def test_in_memory_requests_have_rules_and_states():
    s = InMemoryStore()
    with pytest.raises(ValueError):
        s.create_ai_request("photo", U, 1)                                         # a photo needs its picture
    with pytest.raises(ValueError):
        s.create_ai_request("check", U, 1)                                         # a check needs its assignment
    a = s.create_ai_request("photo", U, 1, picture_id="p1", created_at=NOW)
    b = s.create_ai_request("again", U, 1, assignment_id=5, created_at=NOW)
    assert [r["id"] for r in s.ai_requests(kinds=["photo"])] == [a["id"]] and [r["id"] for r in s.ai_requests(assignment_id=5)] == [b["id"]]
    assert [r["id"] for r in s.ai_requests(picture_id="p1")] == [a["id"]] and s.ai_requests(class_ids=[]) == []
    assert s.start_ai_request(a["id"], "t@x", NOW)["state"] == "processing" and s.start_ai_request(a["id"], "t@x", NOW) is None     # only once
    s.save_ai_request(a["id"], state="failed", failure={"reason": "x"})
    assert s.start_ai_request(a["id"], "t@x", NOW)["failure"] is None                                  # a retry
    assert s.requeue_processing_ai_requests() == 1 and s.get_ai_request(a["id"])["state"] == "waiting"
    with pytest.raises(ValueError):
        s.save_ai_request(a["id"], user_id="x")
    copy = s.get_ai_request(a["id"])
    copy["result"] = {"changed": 1}
    assert s.get_ai_request(a["id"])["result"] is None                                                 # rows come back as copies


def test_in_memory_allowance_never_passes_the_cap():
    s = InMemoryStore()
    assert s.take_ai_allowance("class:1", DAY, 3, 5) and not s.take_ai_allowance("class:1", DAY, 3, 5) and s.take_ai_allowance("class:1", DAY, 2, 5)
    s.give_back_ai_allowance("class:1", DAY, 9)
    assert s.ai_allowance_used("class:1", DAY) == 0 and s.take_ai_allowance("class:1", date(2026, 11, 10), 5, 5)       # another day starts empty


def test_supabase_requests_send_what_they_should():
    s = Recorder([[row()], [row(state="processing")], [row()], [row(state="processing")], [row()], [row(state="waiting")], [{"used": 2}], [], [row(state="declined")]])
    made = s.create_ai_request("photo", U, 1, picture_id="p1", skill_id="sk", created_at=NOW)
    assert s.calls[0][:2] == ("POST", "m2_ai_requests") and s.calls[0][3] == {"kind": "photo", "user_id": U, "class_id": 1, "picture_id": "p1", "assignment_id": None,
                                                                              "skill_id": "sk", "snapshot": None, "created_at": NOW.isoformat()} and made["created_at"] == NOW
    started = s.start_ai_request("r1", "t@x.test", NOW)
    assert s.calls[1][2] == {"id": "eq.r1", "state": "in.(waiting,failed)"} and s.calls[1][3]["state"] == "processing" and started["state"] == "processing"
    listed = s.ai_requests(class_ids=[2, 1], states=["waiting", "failed"], kinds=["photo"], user_id=U, assignment_id=7, picture_id="p1")
    assert s.calls[2][2] == {"select": "*", "order": "created_at,id", "user_id": f"eq.{U}", "class_id": "in.(1,2)", "state": "in.(failed,waiting)",
                             "kind": "in.(photo)", "assignment_id": "eq.7", "picture_id": "eq.p1"} and listed[0]["created_at"] == NOW
    assert s.ai_requests(class_ids=[]) == []
    s2 = Recorder([[{"id": "a"}, {"id": "b"}]])
    assert s2.requeue_processing_ai_requests() == 2 and s2.calls[0][:3] == ("PATCH", "m2_ai_requests", {"state": "eq.processing"})
    s3 = Recorder([True, None, [{"used": 2}]])
    assert s3.take_ai_allowance("class:1", DAY, 1, 5) is True and s3.calls[0][:2] == ("POST", "rpc/m2_ai_take") and s3.calls[0][3] == {"p_scope": "class:1", "p_day": "2026-11-09", "p_n": 1, "p_cap": 5}
    s3.give_back_ai_allowance("class:1", DAY, 1)
    assert s3.calls[1][:2] == ("POST", "rpc/m2_ai_give_back") and s3.ai_allowance_used("class:1", DAY) == 2
    s4 = Recorder([[row(state="declined")]])
    assert s4.save_ai_request("r1", state="declined", teacher_note="x")["state"] == "declined" and s4.calls[0][3] == {"state": "declined", "teacher_note": "x"}
    with pytest.raises(ValueError):
        Recorder([]).save_ai_request("r1", user_id="x")
