"""The developer's prompter (add-prompter): saved texts, the outline, and who may use them."""
from fastapi.testclient import TestClient

from mathly2.ai import FakeAI
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

DEV, DEV2, MGR, TEACHER = "dev@school.test", "dev2@school.test", "mgr@school.test", "t@school.test"
SCRIPT = "Slide 1 — פתיחה\nבוקר טוב לכולם, היום נדבר על תאים.\n\nSlide 2 — סיכום\nתודה רבה."


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def world(ai=None):
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    app = create_app(Settings(developers=frozenset({DEV, DEV2}), teachers=frozenset({TEACHER})), store=store, ai_client=ai or FakeAI())
    return TestClient(app), store


def add(c, body=SCRIPT, title="", who=DEV):
    return c.post("/api/prompter/texts", json={"title": title, "body": body}, headers=auth(who))


def test_only_developers_reach_the_prompter():
    c, _ = world()
    assert c.get("/api/prompter/texts").status_code == 401
    for who in (MGR, TEACHER):
        assert c.get("/api/prompter/texts", headers=auth(who)).status_code == 403
        assert add(c, who=who).status_code == 403
    assert c.get("/api/prompter/texts", headers=auth(DEV)).json() == {"texts": []}


def test_a_saved_text_is_the_accounts_own_on_every_device_newest_first():
    c, _ = world()
    first = add(c, title="  הרצאה   על תאים ").json()["text"]
    assert first["title"] == "הרצאה על תאים"
    second = add(c, body="שורה ראשונה\nעוד").json()["text"]
    assert second["title"] == "שורה ראשונה"                                     # no title: the first line
    assert [t["id"] for t in c.get("/api/prompter/texts", headers=auth(DEV)).json()["texts"]] == [second["id"], first["id"]]
    assert c.get("/api/prompter/texts", headers=auth(DEV2)).json()["texts"] == []                 # another developer's
    assert c.put(f"/api/prompter/texts/{first['id']}", json={"body": "x"}, headers=auth(DEV2)).status_code == 404
    assert c.delete(f"/api/prompter/texts/{first['id']}", headers=auth(DEV2)).status_code == 404


def test_limits_an_empty_text_a_long_title_and_two_hundred_texts():
    c, _ = world()
    assert add(c, body="   ").status_code == 422
    assert len(add(c, title="א" * 300).json()["text"]["title"]) == 120
    assert add(c, body="x" * 100_001).status_code == 413
    for _ in range(199):
        add(c, body="טקסט")
    assert add(c, body="עוד אחד").status_code == 409


def test_the_ai_outline_is_kept_dropped_when_the_text_changes_and_editable():
    fake = FakeAI()
    c, store = world(fake)
    text = add(c).json()["text"]
    made = c.post(f"/api/prompter/texts/{text['id']}/outline", headers=auth(DEV))
    assert made.status_code == 200
    outline = made.json()["text"]["outline"]
    assert "Slide 1 — פתיחה\n• בוקר טוב" in outline and made.json()["text"]["updated_at"] == text["updated_at"]   # the text did not change
    assert fake.calls[-1] == ("outline", SCRIPT)
    assert [r["feature"] for r in store.ai_usage_rows()] == ["prompter"]
    kept = c.put(f"/api/prompter/texts/{text['id']}", json={"title": "חדש", "body": SCRIPT}, headers=auth(DEV)).json()["text"]
    assert kept["outline"] == outline and kept["title"] == "חדש"                 # the same text: the outline stays
    edited = c.put(f"/api/prompter/texts/{text['id']}", json={"body": SCRIPT, "outline": "• משלי"}, headers=auth(DEV)).json()["text"]
    assert edited["outline"] == "• משלי"
    changed = c.put(f"/api/prompter/texts/{text['id']}", json={"body": SCRIPT + "\nעוד שורה"}, headers=auth(DEV)).json()["text"]
    assert changed["outline"] is None                                            # written from the old text: dropped


def test_a_failed_outline_says_why_and_keeps_the_text():
    c, store = world(FakeAI(fail="no_credit"))
    text = add(c).json()["text"]
    got = c.post(f"/api/prompter/texts/{text['id']}/outline", headers=auth(DEV))
    assert got.status_code == 503 and "היתרה" in got.json()["detail"]
    assert c.get("/api/prompter/texts", headers=auth(DEV)).json()["texts"][0]["outline"] is None


def test_deleting_a_text():
    c, _ = world()
    text = add(c).json()["text"]
    assert c.delete(f"/api/prompter/texts/{text['id']}", headers=auth(DEV)).status_code == 204
    assert c.get("/api/prompter/texts", headers=auth(DEV)).json()["texts"] == []
    assert c.delete("/api/prompter/texts/not-an-id", headers=auth(DEV)).status_code == 404
