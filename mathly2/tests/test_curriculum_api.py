"""The curriculum (add-lesson-schedule 2.1, 3.1): a date per lesson, who sets it, and what the path says about it."""
from datetime import timedelta

from mathly2 import clock
from mathly2.tests.test_skills_api import KID, KID_ID, MGR, MON, OTHER, TEACHER, auth, raw, world  # noqa: F401


def rows(client, who=KID):
    return {l["id"]: l for l in client.get("/api/path", headers=auth(who)).json()["lessons"]}


def put(client, dates, who=MGR):
    return client.put("/api/curriculum", json={"dates": dates}, headers=auth(who))


def test_a_manager_sets_changes_and_clears_a_date(world):
    client, _, bank = world
    first, second = bank.lessons[0]["id"], bank.lessons[1]["id"]
    got = client.get("/api/curriculum", headers=auth(MGR)).json()
    assert [r["id"] for r in got] == [l["id"] for l in bank.lessons] and all(r["due_date"] is None for r in got) and got[0]["month"]
    assert put(client, {first: "2026-11-03", second: "2026-12-01"}).json()[0]["due_date"] == "2026-11-03"
    assert put(client, {first: "2026-11-05", second: None}).status_code == 200
    now = {r["id"]: r["due_date"] for r in client.get("/api/curriculum", headers=auth(MGR)).json()}
    assert now[first] == "2026-11-05" and now[second] is None


def test_only_managers_change_it_and_bad_input_is_refused(world):
    client, _, bank = world
    first = bank.lessons[0]["id"]
    for who in (TEACHER, KID, OTHER):
        assert put(client, {first: "2026-11-03"}, who).status_code in (401, 403)
        assert client.get("/api/curriculum", headers=auth(who)).status_code in (401, 403)
    assert put(client, {"no-such-lesson": "2026-11-03"}).status_code == 422
    assert put(client, {first: "3.11"}).status_code == 422
    assert client.get("/api/curriculum", headers=auth(MGR)).json()[0]["due_date"] is None        # nothing changed


def test_a_lesson_is_behind_only_when_dated_past_and_not_completed(world):
    client, store, bank = world
    ids = [l["id"] for l in bank.lessons_with_skills()][:5]
    today = clock.school_day()
    yesterday, tomorrow = (today - timedelta(days=1)).isoformat(), (today + timedelta(days=7)).isoformat()
    put(client, {ids[0]: yesterday, ids[1]: tomorrow, ids[2]: yesterday, ids[3]: yesterday})   # ids[4]: no date
    path = client.get("/api/path", headers=auth()).json()
    by = {l["id"]: l for l in path["lessons"]}
    assert by[ids[0]]["behind"] is True and by[ids[0]]["due_date"] == yesterday
    assert by[ids[1]]["behind"] is False and by[ids[4]]["behind"] is False and by[ids[4]]["due_date"] is None
    # a completed lesson (all skills mastered) is not behind, and neither is one whose quiz was passed
    for skill in by[ids[2]]["skills"]:
        store.save_progress(KID_ID, skill["id"], started_at=MON, mastered_at=MON)
    assert rows(client)[ids[2]]["completed"] is True and rows(client)[ids[2]]["behind"] is False
    assert path["behind"] == 3                                                                  # before the third was completed
    after = client.get("/api/path", headers=auth()).json()
    assert after["behind"] == 2 and {l["id"] for l in after["lessons"] if l["behind"]} == {ids[0], ids[3]}
