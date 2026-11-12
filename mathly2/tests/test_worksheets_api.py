"""Uploading a worksheet and the AI's draft (add-subjects-and-worksheets 5.1-5.3)."""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mathly2 import worksheets
from mathly2.ai import FakeAI
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

MGR, DEV, TEACHER = "mgr@school.test", "dev@school.test", "t@school.test"
DOCX = worksheets.DOCX


def auth(email, kind=None):
    headers = {"Authorization": f"Bearer dev:{email}"}
    if kind:
        headers["Content-Type"] = kind
    return headers


def jpeg(color=(200, 200, 200)):
    out = io.BytesIO()
    Image.new("RGB", (400, 300), color).save(out, "JPEG")
    return out.getvalue()


def pdf(pages=2):
    out = io.BytesIO()
    images = [Image.new("RGB", (600, 800), (255, 255, 255)) for _ in range(pages)]
    images[0].save(out, "PDF", save_all=True, append_images=images[1:])
    return out.getvalue()


def docx_file(text="שאלה 1: מהו התא?"):
    import docx
    document = docx.Document()
    document.add_paragraph(text)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def world(ai=None, inline=True):
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    store.create_class("setup", "מדעים ט'", teacher_email=TEACHER)
    app = create_app(Settings(developers=frozenset({DEV}), teachers=frozenset({TEACHER})), store=store, ai_client=ai or FakeAI())
    if inline:
        app.state.run_worksheet = worksheets.run                        # draft in the request, so a test sees the outcome at once
    return TestClient(app), store


def start(c, who=MGR, **body):
    return c.post("/api/worksheets", json=body or {"new_subject": "מדעים", "icon": "⚗"}, headers=auth(who))


def upload(c, lesson_id, data, kind, who=MGR):
    return c.post(f"/api/worksheets/{lesson_id}/files", content=data, headers=auth(who, kind))


# ---- 5.1 upload ----

def test_a_pdf_for_a_new_subject_creates_the_subject_and_renders_its_pages():
    c, store = world()
    made = start(c)
    assert made.status_code == 201 and made.json()["status"] == "ready" and made.json()["draft"] is None
    assert [s["name"] for s in store.subjects()] == ["מתמטיקה", "מדעים"]
    got = upload(c, made.json()["id"], pdf(3), "application/pdf")
    assert got.status_code == 201 and len(got.json()["pages"]) == 3 and got.json()["sources"] == ["pdf"]
    page = c.get(f"/api/worksheets/{made.json()['id']}/pages/{got.json()['pages'][0]}", headers=auth(MGR))
    assert page.status_code == 200 and page.headers["content-type"] == "image/jpeg"


def test_photos_one_by_one_up_to_ten_and_a_word_document_with_its_text():
    c, store = world()
    lesson = start(c).json()["id"]
    for _ in range(10):
        assert upload(c, lesson, jpeg(), "image/jpeg").status_code == 201
    assert upload(c, lesson, jpeg(), "image/jpeg").status_code == 422                     # an eleventh photo
    assert upload(c, lesson, pdf(), "application/pdf").status_code == 422                  # a PDF after photos
    word = start(c, subject_id=store.subjects()[1]["id"]).json()["id"]
    got = upload(c, word, docx_file(), DOCX)
    assert got.status_code == 201 and got.json()["has_text"] and got.json()["sources"] == ["docx"]
    assert "מהו התא" in c.get(f"/api/worksheets/{word}/text", headers=auth(MGR)).json()["text"]
    assert upload(c, word, jpeg(), "image/jpeg").status_code == 422                        # a Word document is the whole worksheet


def test_a_file_that_is_not_allowed_is_refused_with_what_is_allowed():
    c, _ = world()
    lesson = start(c).json()["id"]
    got = upload(c, lesson, b"a,b\n1,2", "text/csv")
    assert got.status_code == 415 and "PDF" in got.json()["detail"] and "Word" in got.json()["detail"]
    assert upload(c, lesson, b"not a pdf", "application/pdf").status_code == 415
    assert upload(c, lesson, b"not a docx", DOCX).status_code == 400


def test_only_a_manager_or_a_developer_uploads_and_twenty_a_day():
    c, _ = world()
    assert start(c, who=TEACHER).status_code == 403
    sid = start(c, who=DEV).json()["subject_id"]
    for _ in range(20):
        assert start(c, subject_id=sid).status_code == 201
    assert start(c, subject_id=sid).status_code == 429


# ---- 5.2 / 5.3 the draft ----

def test_the_ai_drafts_a_lesson_with_ids_of_the_lesson_and_records_the_cost():
    fake = FakeAI()
    c, store = world(fake)
    lesson = start(c).json()["id"]
    upload(c, lesson, pdf(2), "application/pdf")
    got = c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR))
    assert got.status_code == 200
    read = c.get(f"/api/worksheets/{lesson}", headers=auth(MGR)).json()
    assert read["status"] == "ready" and read["failure"] is None
    draft = read["draft"]
    assert draft["name"] == "תאים" and draft["skills"][0]["id"] == f"w{lesson}_1" and list(draft["mistakes"]) == [f"w{lesson}_m1"]
    questions = draft["skills"][0]["questions"]
    assert len(questions) == 10 and questions[0]["source"] == "sheet" and questions[-1]["source"] == "ai"
    assert questions[0]["choices"][1]["mistake"] == f"w{lesson}_m1"
    assert [r["feature"] for r in store.ai_usage_rows()] == ["worksheet"]
    kind, parts, subject = fake.calls[0]
    assert kind == "draft_lesson" and parts[0]["kind"] == "pdf" and subject == "מדעים"


def test_the_ai_gets_only_the_worksheet_and_the_subjects_name():
    fake = FakeAI()
    c, store = world(fake)
    lesson = start(c).json()["id"]
    upload(c, lesson, docx_file("דף של כיתה ט'3"), DOCX)
    c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR))
    sent = repr(fake.calls[0])
    for private in (MGR, TEACHER, "מדעים ט'", "school.test"):
        assert private not in sent


@pytest.mark.parametrize("reason, words", [("unreadable", "לא הצלחנו לקרוא"), ("api_key_missing", "אין מפתח"), ("no_credit", "היתרה"),
                                           ("overloaded", "עמוס"), ("bad_output", "לא הייתה שמישה")])
def test_a_failed_draft_says_why_in_words_and_retrying_needs_no_new_upload(reason, words):
    fake = FakeAI()
    fake.fail_draft = [reason]
    c, store = world(fake)
    lesson = start(c).json()["id"]
    upload(c, lesson, pdf(), "application/pdf")
    c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR))
    failed = c.get(f"/api/worksheets/{lesson}", headers=auth(MGR)).json()
    assert failed["status"] == "failed" and words in failed["failure"]["what"] and failed["failure"]["todo"]
    assert c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR)).status_code == 200      # "נסו שוב": the same files
    assert c.get(f"/api/worksheets/{lesson}", headers=auth(MGR)).json()["status"] == "ready"
    assert len(fake.calls) == 2 and store.get_lesson(lesson)["files"][0]["kind"] == "pdf"


def test_drafting_needs_a_file_first_and_runs_in_the_background():
    c, store = world(inline=False)
    lesson = start(c).json()["id"]
    assert c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR)).status_code == 422
    upload(c, lesson, jpeg(), "image/jpeg")
    assert c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR)).json()["status"] == "drafting"
    for _ in range(100):
        if c.get(f"/api/worksheets/{lesson}", headers=auth(MGR)).json()["status"] != "drafting":
            break
        time.sleep(0.05)
    assert c.get(f"/api/worksheets/{lesson}", headers=auth(MGR)).json()["status"] == "ready"


def test_a_lesson_left_drafting_by_a_restart_can_be_tried_again():
    c, store = world()
    lesson = start(c).json()["id"]
    upload(c, lesson, pdf(), "application/pdf")
    store.save_lesson(lesson, status="drafting")                                         # the server stopped mid-draft
    assert worksheets.recover_after_restart(store) == 1
    failed = c.get(f"/api/worksheets/{lesson}", headers=auth(MGR)).json()
    assert failed["status"] == "failed" and failed["failure"]["reason"] == "interrupted"
    c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR))
    assert c.get(f"/api/worksheets/{lesson}", headers=auth(MGR)).json()["status"] == "ready"


def test_a_draft_never_reaches_a_student():
    c, store = world()
    lesson = start(c).json()["id"]
    upload(c, lesson, pdf(), "application/pdf")
    c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR))
    assert c.app.state.bank.lessons_of_subject(store.get_lesson(lesson)["subject_id"]) == []


# ---- 6.1 reading and saving the draft ----

def drafted(c, subject_id=None):
    lesson = (start(c, subject_id=subject_id) if subject_id else start(c)).json()["id"]
    upload(c, lesson, pdf(), "application/pdf")
    c.post(f"/api/worksheets/{lesson}/draft", headers=auth(MGR))
    return lesson, c.get(f"/api/subjects/lessons/{lesson}", headers=auth(MGR)).json()["draft"]


def test_the_whole_draft_is_saved_and_read_back_with_new_parts_given_ids():
    c, store = world()
    lesson, draft = drafted(c)
    draft["name"] = "התא החי"
    draft["skills"][0]["questions"][0]["choices"][0], draft["skills"][0]["questions"][0]["choices"][1] = (
        {**draft["skills"][0]["questions"][0]["choices"][1], "correct": True, "mistake": None},
        {"text": draft["skills"][0]["questions"][0]["choices"][0]["text"], "mistake": "new-mistake"})
    draft["mistakes"]["new-mistake"] = {"name": "", "tip": ""}
    draft["skills"].append({"name": "קרום התא", "questions": [{"question": "חדשה", "source": "person", "choices": [{"text": "כן", "correct": True}]}]})
    saved = c.put(f"/api/subjects/lessons/{lesson}/draft", json={"lesson": draft}, headers=auth(MGR))
    assert saved.status_code == 200
    back = c.get(f"/api/subjects/lessons/{lesson}", headers=auth(MGR)).json()["draft"]
    assert back["name"] == "התא החי" and back["skills"][1]["id"] == f"w{lesson}_2"
    assert f"w{lesson}_m2" in back["mistakes"] and back["skills"][0]["questions"][0]["choices"][1]["mistake"] == f"w{lesson}_m2"
    assert back["skills"][1]["questions"][0]["source"] == "person"
    assert store.get_lesson(lesson)["published"] is None                                    # saving never publishes


def test_an_unfinished_draft_saves_but_a_broken_shape_does_not_and_others_are_refused():
    c, _ = world()
    lesson, draft = drafted(c)
    draft["skills"][0]["questions"][0]["choices"] = [{"text": "רק אחת"}]                    # unfinished: no right answer yet
    assert c.put(f"/api/subjects/lessons/{lesson}/draft", json={"lesson": draft}, headers=auth(MGR)).status_code == 200
    broken = c.put(f"/api/subjects/lessons/{lesson}/draft", json={"lesson": {"name": "x", "skills": "nope"}}, headers=auth(MGR))
    assert broken.status_code == 422
    assert c.put(f"/api/subjects/lessons/{lesson}/draft", json={"lesson": draft}, headers=auth(TEACHER)).status_code == 403
    assert c.get(f"/api/subjects/lessons/{lesson}", headers=auth(TEACHER)).status_code == 403


# ---- 7.1 publishing, 7.2 editing a published lesson and unpublishing ----

def publish(c, lesson, who=MGR):
    return c.post(f"/api/subjects/lessons/{lesson}/publish", headers=auth(who))


def test_publishing_lists_every_failing_check_with_where_it_is():
    c, store = world()
    lesson, draft = drafted(c)
    q = draft["skills"][0]["questions"]
    q[3]["choices"][1]["mistake"] = ""                                                    # a wrong choice without a mistake
    q[4]["choices"][0]["correct"] = False                                                 # no right answer
    draft["skills"].append({"name": "", "questions": []})                                 # a skill with no name and no questions
    draft["mistakes"][f"w{lesson}_m1"]["tip"] = ""                                         # a mistake without a tip
    c.put(f"/api/subjects/lessons/{lesson}/draft", json={"lesson": draft}, headers=auth(MGR))
    refused = publish(c, lesson)
    assert refused.status_code == 422
    problems = refused.json()["detail"]["problems"]
    assert "מיומנות 1, שאלה 4, תשובה 2: לתשובה השגויה אין טעות" in problems
    assert any(p.startswith("מיומנות 1, שאלה 5: צריכה תשובה נכונה אחת") for p in problems)
    assert "מיומנות 2: אין שם" in problems and "מיומנות 2: יש 0 שאלות, צריך לפחות 5" in problems
    assert any("חסר שם או טיפ" in p for p in problems)
    assert store.get_lesson(lesson)["published"] is None


def published_lesson(c, store):
    lesson, draft = drafted(c)
    assert publish(c, lesson).status_code == 200
    sid = store.get_lesson(lesson)["subject_id"]
    klass = store.create_class("setup", "ט'1", teacher_email=TEACHER, subjects=[sid])
    store.add_member(klass["id"], "kid@school.test")
    return lesson, sid, klass


def test_a_published_lesson_reaches_a_studying_student_at_once_last_in_its_subject():
    c, store = world()
    lesson, sid, _ = published_lesson(c, store)
    second, _ = drafted(c, sid)
    assert publish(c, second).status_code == 200
    assert [u["id"] for u in c.app.state.bank.lessons_of_subject(sid)] == [f"w{lesson}", f"w{second}"]
    path = c.get(f"/api/path?subject={sid}", headers=auth("kid@school.test")).json()
    assert [l["id"] for l in path["lessons"]] == [f"w{lesson}", f"w{second}"]
    assert c.post(f"/api/lessons/w{lesson}/quiz/start", headers=auth("kid@school.test")).status_code == 200


def test_editing_a_published_question_makes_a_new_question_and_keeps_old_answers():
    c, store = world()
    lesson, sid, _ = published_lesson(c, store)
    kid = "kid@school.test"
    skill = f"w{lesson}_1"
    first = c.get(f"/api/skills/{skill}", headers=auth(kid)).json()["question"]["key"]
    c.post(f"/api/skills/{skill}/answer", json={"question_key": first, "choice": 0}, headers=auth(kid))
    draft = c.get(f"/api/subjects/lessons/{lesson}", headers=auth(MGR)).json()["draft"]
    draft["skills"][0]["questions"] = [{**q, "question": q["question"] + " (מתוקן)"} for q in draft["skills"][0]["questions"]]
    c.put(f"/api/subjects/lessons/{lesson}/draft", json={"lesson": draft}, headers=auth(MGR))
    assert first in c.app.state.bank.question_keys(skill)                                    # students keep the published copy until publishing
    assert publish(c, lesson).status_code == 200
    assert first not in c.app.state.bank.question_keys(skill)                                # an edited question is a new question
    import uuid
    kid_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, kid))
    assert [a["question_key"] for a in store.answers_of(kid_id, skill)] == [first]          # the earlier answer stays in the history


def test_unpublishing_hides_the_lesson_and_keeps_progress_but_not_while_a_coming_test_covers_it():
    from datetime import date, timedelta
    c, store = world()
    lesson, sid, klass = published_lesson(c, store)
    kid = "kid@school.test"
    import uuid
    kid_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, kid))
    store.save_progress(kid_id, f"w{lesson}_1", started_at="then", mastered_at="then")
    test = store.create_test(klass["id"], date.today() + timedelta(days=30), [f"w{lesson}"], TEACHER, subject_id=sid)
    refused = c.post(f"/api/subjects/lessons/{lesson}/unpublish", headers=auth(MGR))
    assert refused.status_code == 409 and "ט'1" in refused.json()["detail"]                 # names the test
    store.remove_test(test["id"])
    assert c.post(f"/api/subjects/lessons/{lesson}/unpublish", headers=auth(MGR)).json()["published"] is False
    assert c.app.state.bank.lessons_of_subject(sid) == []
    assert c.get(f"/api/path?subject={sid}", headers=auth(kid)).json()["lessons"] == []
    assert store.get_progress(kid_id, f"w{lesson}_1")["mastered_at"] == "then"
    assert publish(c, lesson).status_code == 200                                            # published again: the progress shows
    path = c.get(f"/api/path?subject={sid}", headers=auth(kid)).json()
    assert path["lessons"][0]["mastered"] == 1


def test_only_managers_and_developers_publish():
    c, store = world()
    lesson, _ = drafted(c)
    assert publish(c, lesson, who=TEACHER).status_code == 403
