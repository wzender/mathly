"""Assignments through the API: the teacher's side (add-written-work 2.2); the student's and the inbox are below."""
import io
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

TEACHER, OTHER_TEACHER, KID, KID2, OUTSIDER, MGR, DEV = ("t@school.test", "t2@school.test", "kid@school.test", "kid2@school.test", "out@school.test",
                                                           "mgr@school.test", "dev@school.test")
MON = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def uid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def image(fmt="JPEG", color="red"):
    out = io.BytesIO()
    Image.new("RGB", (80, 50), color).save(out, fmt)
    return out.getvalue()


def make_pdf(pages):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(200, 300)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture
def world(bank, monkeypatch):
    """Class A (teacher T; students KID, KID2) studies a lesson with an authored written quiz and one without; class B (teacher T2; OUTSIDER)."""
    with_quiz = [u["id"] for u in bank.data["units"] if u.get("quiz")]
    without = next(u["id"] for u in bank.data["units"] if not u.get("quiz"))
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    a = store.create_class("setup", "A", lessons=[with_quiz[0], without], teacher_email=TEACHER)
    b = store.create_class("setup", "B", lessons=[with_quiz[1]], teacher_email=OTHER_TEACHER)
    for email in (KID, KID2):
        store.add_member(a["id"], email)
        store.link_user(email, uid(email))
    store.add_member(b["id"], OUTSIDER)
    client = TestClient(create_app(Settings(developers=frozenset({DEV})), bank=bank, store=store))
    moment = {"now": MON}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    client.set_time = lambda value: moment.update(now=value)
    client.store, client.a, client.b, client.quiz_lesson, client.plain_lesson, client.other_quiz = store, a, b, with_quiz[0], without, with_quiz[1]
    return client


def upload_pages(client, data, kind="image/jpeg", who=TEACHER):
    return client.post("/api/assignments/pages", content=data, headers={**auth(who), "Content-Type": kind})


def give(client, who=TEACHER, class_id=None, **body):
    due = (clock.now() + 7 * DAY).date().isoformat()
    return client.post(f"/api/classes/{class_id or client.a['id']}/assignments", json={"title": "משימה", "due_date": due, **body}, headers=auth(who))


# --- 2.2 giving: the five sources ---

def test_from_an_uploaded_image_the_board_or_a_photo_the_pages_become_the_assignments_pages(world):
    first = upload_pages(world, image("JPEG")).json()["pictures"]
    second = upload_pages(world, image("PNG", "blue"), "image/png").json()["pictures"]         # what the board sends: a PNG page
    assert len(first) == 1 and len(second) == 1
    got = give(world, kind="pages", pages=first + second, note="לפתור עד יום ד׳")
    assert got.status_code == 201
    body = got.json()
    assert body["kind"] == "pages" and body["pages"] == first + second and body["note"] == "לפתור עד יום ד׳" and body["days_left"] == 7
    assert body["students"] == 2 and body["handed_in"] == 0 and body["graded"] == 0 and body["class"]["name"] == "A"
    assert all(world.store.get_picture(p)["kind"] == "page" and world.store.get_picture(p)["owner_id"] == uid(TEACHER) for p in first + second)


def test_a_pdf_becomes_one_page_picture_per_sheet(world):
    ids = upload_pages(world, make_pdf(3), "application/pdf").json()["pictures"]
    assert len(ids) == 3 and len(set(ids)) == 3
    assert upload_pages(world, b"hello", "application/pdf").status_code == 415
    assert upload_pages(world, b"nonsense", "image/jpeg").status_code == 400
    assert give(world, kind="pages", pages=ids).json()["pages"] == ids


def test_from_the_banks_written_quiz_only_for_a_class_lesson_that_has_one(world, bank):
    got = give(world, kind="quiz", quiz_lesson=world.quiz_lesson, title="בוחן כתוב")
    assert got.status_code == 201 and got.json()["quiz_lesson"]["id"] == world.quiz_lesson and got.json()["quiz_lesson"]["name"]
    assert give(world, kind="quiz", quiz_lesson=world.plain_lesson).status_code == 422          # a class lesson with no written quiz
    assert give(world, kind="quiz", quiz_lesson=world.other_quiz).status_code == 422            # a quiz of a lesson the class does not study
    assert give(world, kind="quiz").status_code == 422


def test_an_exercise_test_of_a_test_of_the_class_can_be_sent_as_an_assignment(world):
    test = world.store.create_test(world.a["id"], clock.school_day() + 10 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    other = world.store.create_test(world.b["id"], clock.school_day() + 10 * DAY, [world.other_quiz], OTHER_TEACHER, created_at=clock.now())
    got = give(world, kind="exercise_test", test_id=test["id"], exercise_number=2)
    assert got.status_code == 201 and got.json()["test"] == {"id": test["id"], "number": 2, "date": test["date"].isoformat()} and got.json()["done"] == 0
    assert give(world, kind="exercise_test", test_id=other["id"], exercise_number=1).status_code == 422        # another class's test
    assert give(world, kind="exercise_test", test_id=test["id"], exercise_number=3).status_code == 422
    assert give(world, kind="exercise_test", test_id=999, exercise_number=1).status_code == 422
    world.store.remove_test(test["id"])
    assert give(world, kind="exercise_test", test_id=test["id"], exercise_number=1).status_code == 422


def test_giving_needs_a_class_the_teacher_teaches_a_future_date_and_pages_that_are_their_own(world):
    assert give(world, who=OTHER_TEACHER, kind="quiz", quiz_lesson=world.quiz_lesson).status_code == 404
    assert give(world, who=KID, kind="quiz", quiz_lesson=world.quiz_lesson).status_code == 403
    assert give(world, who=MGR, kind="quiz", quiz_lesson=world.quiz_lesson).status_code == 403
    past = world.post(f"/api/classes/{world.a['id']}/assignments", json={"title": "x", "due_date": (clock.now() - DAY).date().isoformat(), "kind": "quiz",
                                                                       "quiz_lesson": world.quiz_lesson}, headers=auth(TEACHER))
    assert past.status_code == 422
    assert give(world, kind="pages", pages=[]).status_code == 422
    mine = upload_pages(world, image()).json()["pictures"]
    theirs = upload_pages(world, image(), who=OTHER_TEACHER).json()["pictures"]
    assert give(world, kind="pages", pages=theirs).status_code == 422                          # a page someone else uploaded
    answer = world.post("/api/pictures", content=image(), headers={**auth(KID), "Content-Type": "image/jpeg"}).json()["id"]
    assert give(world, kind="pages", pages=[answer]).status_code == 422                        # an answer picture is not a page
    assert give(world, kind="pages", pages=[str(uuid.uuid4())]).status_code == 422
    assert give(world, kind="pages", pages=mine, title="").status_code == 422
    assert give(world, who=DEV, kind="quiz", quiz_lesson=world.quiz_lesson).status_code == 201     # a developer may give to any class


def test_the_list_has_counts_and_a_developer_sees_every_class(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    world.store.save_submission(quiz["id"], uid(KID), pictures=["p1"])
    world.store.save_submission(quiz["id"], uid(KID2), pictures=["p2"], state="graded", grade=80)
    listed = world.get("/api/teaching/assignments", headers=auth(TEACHER)).json()
    assert [c["class"]["name"] for c in listed] == ["A"]
    one = listed[0]["assignments"][0]
    assert (one["handed_in"], one["graded"], one["returned"], one["waiting"], one["students"]) == (1, 1, 0, 1, 2)
    assert listed[0]["class"]["lessons"]
    assert [c["class"]["name"] for c in world.get("/api/teaching/assignments", headers=auth(DEV)).json()] == ["A", "B"]
    assert world.get("/api/teaching/assignments", headers=auth(OTHER_TEACHER)).json()[0]["assignments"] == []


def test_removing_an_assignment_hides_it_and_keeps_the_grades_already_given(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    world.store.save_submission(quiz["id"], uid(KID), pictures=["p1"], state="graded", grade=90, teacher_note="יפה")
    assert world.delete(f"/api/assignments/{quiz['id']}", headers=auth(OTHER_TEACHER)).status_code == 404
    assert world.delete(f"/api/assignments/{quiz['id']}", headers=auth(KID)).status_code == 403
    assert world.delete(f"/api/assignments/{quiz['id']}", headers=auth(TEACHER)).status_code == 204
    assert world.get("/api/teaching/assignments", headers=auth(TEACHER)).json()[0]["assignments"] == []
    assert world.delete(f"/api/assignments/{quiz['id']}", headers=auth(TEACHER)).status_code == 404
    kept = world.store.get_submission(quiz["id"], uid(KID))
    assert (kept["grade"], kept["teacher_note"]) == (90, "יפה") and world.store.get_assignment(quiz["id"])["removed_at"] is not None


# --- 2.3 the student's side ---

def answer_picture(client, who=KID):
    got = client.post("/api/pictures", content=image(), headers={**auth(who), "Content-Type": "image/jpeg"})
    assert got.status_code == 201, got.text
    return got.json()["id"]


def hand(client, assignment_id, pictures, who=KID):
    return client.post(f"/api/assignments/{assignment_id}/submission", json={"pictures": pictures}, headers=auth(who))


def mine(client, who=KID):
    return client.get("/api/assignments", headers=auth(who)).json()


def test_a_student_sees_only_their_classes_assignments_with_state_and_due_date(world):
    a = give(world, kind="quiz", quiz_lesson=world.quiz_lesson, title="בוחן כתוב").json()
    listed = mine(world)
    assert [x["id"] for x in listed] == [a["id"]] and listed[0]["state"] == "not_handed" and listed[0]["days_left"] == 7 and listed[0]["class"]["name"] == "A"
    assert mine(world, KID2)[0]["id"] == a["id"] and mine(world, OUTSIDER) == []                      # another class sees nothing
    assert world.get(f"/api/assignments/{a['id']}", headers=auth(OUTSIDER)).status_code == 404


def test_a_written_quiz_shows_its_questions_with_points_and_a_pages_assignment_its_pages(world, bank):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    detail = world.get(f"/api/assignments/{quiz['id']}", headers=auth(KID)).json()
    questions = detail["quiz"]["questions"]
    assert len(questions) == 4 and sum(q["points"] for q in questions) == 100 == detail["quiz"]["points"] and detail["quiz"]["minutes"] == 45
    assert all(q["question"] for q in questions)
    pages = upload_pages(world, image()).json()["pictures"]
    sheet = give(world, kind="pages", pages=pages).json()
    assert world.get(f"/api/assignments/{sheet['id']}", headers=auth(KID)).json()["pages"] == pages
    assert world.get(f"/api/pictures/{pages[0]}", headers=auth(KID)).status_code == 200            # the class's students read the pages


def test_handing_in_one_to_ten_of_the_students_own_answer_pictures(world):
    a = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    pics = [answer_picture(world) for _ in range(3)]
    got = hand(world, a["id"], pics)
    assert got.status_code == 200 and got.json()["state"] == "handed_in" and got.json()["late"] is False
    detail = world.get(f"/api/assignments/{a['id']}", headers=auth(KID)).json()
    assert [p["id"] for p in detail["pictures"]] == pics and detail["state"] == "handed_in"
    assert hand(world, a["id"], []).status_code == 422 and hand(world, a["id"], [answer_picture(world) for _ in range(11)]).status_code == 422
    assert hand(world, a["id"], [answer_picture(world, KID2)]).status_code == 422                    # someone else's picture
    page = upload_pages(world, image()).json()["pictures"][0]
    assert hand(world, a["id"], [page]).status_code == 422                                           # a page is not an answer
    assert hand(world, a["id"], [str(uuid.uuid4())]).status_code == 422
    gone = answer_picture(world)
    world.store.mark_picture_deleted(gone)
    assert hand(world, a["id"], [gone]).status_code == 422
    assert world.get(f"/api/assignments/{a['id']}", headers=auth(KID)).json()["pictures"] == detail["pictures"]    # refused tries changed nothing
    assert hand(world, a["id"], pics, who=OUTSIDER).status_code == 404


def test_a_handed_in_submission_can_be_replaced_a_returned_one_handed_in_again_and_a_graded_one_not_changed(world):
    a = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    first = answer_picture(world)
    hand(world, a["id"], [first])
    second = answer_picture(world)
    assert hand(world, a["id"], [second]).json()["state"] == "handed_in"                              # replaced while handed in
    assert [p["id"] for p in world.get(f"/api/assignments/{a['id']}", headers=auth(KID)).json()["pictures"]] == [second]
    sub = world.store.get_submission(a["id"], uid(KID))
    world.store.save_submission(a["id"], uid(KID), state="returned", teacher_note="חסר נימוק בסעיף 2", checked_by=TEACHER)
    shown = world.get(f"/api/assignments/{a['id']}", headers=auth(KID)).json()
    assert shown["state"] == "returned" and shown["teacher_note"] == "חסר נימוק בסעיף 2" and mine(world)[0]["state"] == "returned"
    third = answer_picture(world)
    assert hand(world, a["id"], [third]).json()["state"] == "handed_in"                               # handed in again
    world.store.save_submission(a["id"], uid(KID), state="graded", grade=88, teacher_note="יפה")
    assert hand(world, a["id"], [answer_picture(world)]).status_code == 409                          # graded: no more changes
    done = world.get(f"/api/assignments/{a['id']}", headers=auth(KID)).json()
    assert (done["state"], done["grade"], done["teacher_note"]) == ("graded", 88, "יפה") and sub["id"] == world.store.get_submission(a["id"], uid(KID))["id"]


def test_a_late_hand_in_is_accepted_and_marked_late(world):
    a = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    world.set_time(MON + 9 * DAY)                                                                     # two days after the due date
    assert mine(world)[0]["overdue"] is True and mine(world)[0]["days_left"] == -2
    got = hand(world, a["id"], [answer_picture(world)])
    assert got.status_code == 200 and got.json()["late"] is True and got.json()["overdue"] is False


def test_an_exercise_test_assignment_is_done_after_the_student_took_it_with_the_best_grade_and_cannot_be_handed_in(world):
    test = world.store.create_test(world.a["id"], clock.school_day() + 10 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    a = give(world, kind="exercise_test", test_id=test["id"], exercise_number=1).json()
    assert mine(world)[0]["state"] == "not_done" and mine(world)[0]["test"] == {"id": test["id"], "number": 1}
    assert hand(world, a["id"], [answer_picture(world)]).status_code == 422
    for grade in (60, 85):
        row = world.store.create_attempt(uid(KID), "exercise_test", f"{test['id']}:1", MON, MON + timedelta(minutes=45), [])
        world.store.save_attempt(row["id"], submitted_at=MON + timedelta(minutes=5), grade=grade)
    other = world.store.create_attempt(uid(KID), "exercise_test", f"{test['id']}:2", MON, MON + timedelta(minutes=45), [])
    world.store.save_attempt(other["id"], submitted_at=MON, grade=99)                                  # a different exercise test
    done = mine(world)[0]
    assert done["state"] == "done" and done["grade"] == 85
    assert mine(world, KID2)[0]["state"] == "not_done"
    teacher_view = world.get("/api/teaching/assignments", headers=auth(TEACHER)).json()[0]["assignments"][0]
    assert teacher_view["done"] == 1 and "waiting" not in teacher_view                                 # nothing waits in an inbox for it


def test_open_assignments_come_first_by_due_date_and_removed_ones_are_gone(world):
    far = give(world, kind="quiz", quiz_lesson=world.quiz_lesson, title="רחוק").json()
    near = world.post(f"/api/classes/{world.a['id']}/assignments", json={"title": "קרוב", "due_date": (clock.now() + 2 * DAY).date().isoformat(), "kind": "quiz",
                                                                        "quiz_lesson": world.quiz_lesson}, headers=auth(TEACHER)).json()
    done = give(world, kind="quiz", quiz_lesson=world.quiz_lesson, title="הוגש").json()
    hand(world, done["id"], [answer_picture(world)])
    world.store.save_submission(done["id"], uid(KID), state="graded", grade=70)
    assert [x["title"] for x in mine(world)] == ["קרוב", "רחוק", "הוגש"]
    world.delete(f"/api/assignments/{near['id']}", headers=auth(TEACHER))
    assert [x["title"] for x in mine(world)] == ["רחוק", "הוגש"] and world.get(f"/api/assignments/{near['id']}", headers=auth(KID)).status_code == 404
    assert far["id"] != done["id"]


# --- 2.4 the inbox and checking ---

def inbox(client, who=TEACHER):
    return client.get("/api/teaching/inbox", headers=auth(who)).json()


def submit(client, assignment, who, day_offset=0):
    """A student hands in at a given time; returns the submission row."""
    client.set_time(MON + day_offset * DAY)
    got = hand(client, assignment, [answer_picture(client, who)], who)
    assert got.status_code == 200
    return client.store.get_submission(assignment, uid(who))


def test_the_inbox_lists_what_waits_oldest_first_and_a_returned_one_is_not_in_it(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    tuesday = submit(world, quiz["id"], KID2, 1)                                                      # KID2 hands in on Tuesday
    monday = submit(world, quiz["id"], KID, 0)                                                        # KID's was Monday: first in the inbox even though made second
    items = inbox(world)
    assert [i["id"] for i in items] == [monday["id"], tuesday["id"]] and [i["student"] for i in items] == [KID, KID2]
    assert items[0]["kind"] == "submission" and items[0]["assignment"]["title"] == "משימה" and items[0]["assignment"]["class"]["name"] == "A" and items[0]["pictures"]
    world.store.save_submission(quiz["id"], uid(KID), state="returned", teacher_note="תקנו")
    assert [i["id"] for i in inbox(world)] == [tuesday["id"]]
    assert inbox(world, OTHER_TEACHER) == [] and [i["id"] for i in inbox(world, DEV)] == [tuesday["id"]]


def test_the_teacher_opens_a_submission_and_grades_it_and_the_student_sees_grade_and_note(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    sub = submit(world, quiz["id"], KID)
    opened = world.get(f"/api/submissions/{sub['id']}", headers=auth(TEACHER)).json()
    assert opened["state"] == "handed_in" and len(opened["quiz"]["questions"]) == 4 and opened["pictures"] == [{"id": sub["pictures"][0], "deleted": False}]
    assert world.get(f"/api/pictures/{sub['pictures'][0]}", headers=auth(TEACHER)).status_code == 200      # the teacher reads the answer
    graded = world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 85, "note": "נימוק יפה", "seen": opened["seen"]}, headers=auth(TEACHER))
    assert graded.status_code == 200 and graded.json() == {"id": sub["id"], "state": "graded", "grade": 85}
    assert inbox(world) == []
    mine_now = mine(world)[0]
    assert (mine_now["state"], mine_now["grade"], mine_now["teacher_note"]) == ("graded", 85, "נימוק יפה")
    row = world.store.get_submission(quiz["id"], uid(KID))
    assert row["checked_by"] == TEACHER and row["checked_at"] is not None


def test_a_grade_is_a_whole_number_from_0_to_100(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    sub = submit(world, quiz["id"], KID)
    seen = sub["handed_at"].isoformat()
    for bad in (101, -1, 85.5, "גבוה"):
        assert world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": bad, "seen": seen}, headers=auth(TEACHER)).status_code == 422
    assert world.store.get_submission(quiz["id"], uid(KID))["state"] == "handed_in"
    assert world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 0, "seen": seen}, headers=auth(TEACHER)).status_code == 200          # the edges
    other = submit(world, quiz["id"], KID2)
    assert world.post(f"/api/submissions/{other['id']}/grade", json={"grade": 100, "seen": other["handed_at"].isoformat()}, headers=auth(TEACHER)).status_code == 200


def test_sending_back_needs_a_note_and_the_student_then_hands_in_again(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    sub = submit(world, quiz["id"], KID)
    seen = sub["handed_at"].isoformat()
    assert world.post(f"/api/submissions/{sub['id']}/return", json={"note": "", "seen": seen}, headers=auth(TEACHER)).status_code == 422
    assert world.post(f"/api/submissions/{sub['id']}/return", json={"note": "   ", "seen": seen}, headers=auth(TEACHER)).status_code == 422
    sent = world.post(f"/api/submissions/{sub['id']}/return", json={"note": "חסר נימוק בסעיף 2", "seen": seen}, headers=auth(TEACHER))
    assert sent.status_code == 200 and sent.json()["state"] == "returned" and inbox(world) == []
    shown = mine(world)[0]
    assert shown["state"] == "returned" and shown["teacher_note"] == "חסר נימוק בסעיף 2"
    submit(world, quiz["id"], KID, 1)                                                                  # handed in again: back in the inbox
    assert [i["id"] for i in inbox(world)] == [sub["id"]]


def test_a_stale_view_a_second_check_and_another_classs_teacher_are_refused(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    sub = submit(world, quiz["id"], KID)
    seen = sub["handed_at"].isoformat()
    submit(world, quiz["id"], KID, 1)                                                                  # the student replaced it after the teacher opened it
    stale = world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 70, "seen": seen}, headers=auth(TEACHER))
    assert stale.status_code == 409 and "השתנתה" in stale.json()["detail"]
    fresh = world.store.get_submission(quiz["id"], uid(KID))["handed_at"].isoformat()
    assert world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 70, "seen": fresh}, headers=auth(OTHER_TEACHER)).status_code == 404
    assert world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 70, "seen": fresh}, headers=auth(KID)).status_code == 403
    assert world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 70, "seen": "not a time"}, headers=auth(TEACHER)).status_code == 422
    assert world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 70, "seen": fresh}, headers=auth(TEACHER)).status_code == 200
    assert world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 90, "seen": fresh}, headers=auth(TEACHER)).status_code == 409     # already checked
    assert world.get("/api/submissions/999", headers=auth(TEACHER)).status_code == 404


def test_exercise_test_assignments_never_reach_the_inbox_and_removed_assignments_leave_it(world):
    test = world.store.create_test(world.a["id"], clock.school_day() + 10 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    give(world, kind="exercise_test", test_id=test["id"], exercise_number=1)
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    sub = submit(world, quiz["id"], KID)
    assert [i["id"] for i in inbox(world)] == [sub["id"]]
    world.delete(f"/api/assignments/{quiz['id']}", headers=auth(TEACHER))
    assert inbox(world) == []


def test_the_grades_list_has_graded_assignments_and_done_exercise_tests_and_a_removed_one_keeps_its_grade(world):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson, title="בוחן כתוב").json()
    waiting = give(world, kind="quiz", quiz_lesson=world.quiz_lesson, title="עוד לא נבדק").json()
    sub = submit(world, quiz["id"], KID)
    submit(world, waiting["id"], KID)
    assert world.get("/api/grades", headers=auth(KID)).json()["assignments"] == []                      # nothing graded yet
    world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 92, "note": "יפה מאוד", "seen": sub["handed_at"].isoformat()}, headers=auth(TEACHER))
    test = world.store.create_test(world.a["id"], clock.school_day() + 10 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    exam = give(world, kind="exercise_test", test_id=test["id"], exercise_number=1, title="תרגול").json()
    row = world.store.create_attempt(uid(KID), "exercise_test", f"{test['id']}:1", MON, MON + timedelta(minutes=45), [])
    world.store.save_attempt(row["id"], submitted_at=MON, grade=77)
    got = world.get("/api/grades", headers=auth(KID)).json()["assignments"]
    assert {(g["assignment"]["title"], g["grade"], g["note"]) for g in got} == {("בוחן כתוב", 92, "יפה מאוד"), ("תרגול", 77, "")}
    world.delete(f"/api/assignments/{quiz['id']}", headers=auth(TEACHER))
    kept = [g for g in world.get("/api/grades", headers=auth(KID)).json()["assignments"] if g["assignment"]["title"] == "בוחן כתוב"]
    assert kept[0]["grade"] == 92 and kept[0]["assignment"]["removed"] is True and exam["id"]
    assert world.get("/api/grades", headers=auth(KID2)).json()["assignments"] == []


# --- 2.7 deleting a student's pictures on request, and the hourly cleanup ---

def handed_in_with_pictures(world, who=KID):
    quiz = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    pics = [answer_picture(world, who), answer_picture(world, who)]
    hand(world, quiz["id"], pics, who)
    world.store.save_submission(quiz["id"], uid(who), state="graded", grade=88, teacher_note="יפה")
    return quiz, pics


def delete_pictures(world, who, email=KID, class_id=None):
    return world.delete(f"/api/classes/{class_id or world.a['id']}/pictures/{email}", headers=auth(who))


def test_the_classs_teacher_a_manager_and_a_developer_can_delete_a_students_pictures_and_the_grade_stays(world):
    for who in (TEACHER, MGR, DEV):
        quiz, pics = handed_in_with_pictures(world)
        got = delete_pictures(world, who)
        assert got.status_code == 200 and got.json() == {"deleted": 2}, who
        assert all(world.store.get_picture(p)["deleted_at"] for p in pics)
        assert world.get(f"/api/pictures/{pics[0]}", headers=auth(KID)).status_code == 410           # gone for the student too
        sub = world.store.get_submission(quiz["id"], uid(KID))
        assert (sub["state"], sub["grade"], sub["teacher_note"]) == ("graded", 88, "יפה")             # the grade and note stay
        shown = world.get(f"/api/assignments/{quiz['id']}", headers=auth(KID)).json()
        assert shown["grade"] == 88 and all(p["deleted"] for p in shown["pictures"])
        world.delete(f"/api/assignments/{quiz['id']}", headers=auth(TEACHER))


def test_another_classs_teacher_a_student_and_a_missing_student_cannot(world):
    handed_in_with_pictures(world)
    assert delete_pictures(world, OTHER_TEACHER).status_code == 404
    assert delete_pictures(world, KID2).status_code == 403
    assert delete_pictures(world, KID).status_code == 403
    assert delete_pictures(world, TEACHER, email="nobody@school.test").status_code == 404
    assert delete_pictures(world, TEACHER, class_id=999).status_code == 404
    assert len(world.store.pictures()) >= 2 and all(not p["deleted_at"] for p in world.store.pictures())


def test_only_that_students_pictures_for_that_class_go(world):
    quiz, mine_pics = handed_in_with_pictures(world, KID)
    other_quiz, theirs = handed_in_with_pictures(world, KID2)
    assert delete_pictures(world, TEACHER, KID).json() == {"deleted": 2}
    assert all(not world.store.get_picture(p)["deleted_at"] for p in theirs) and other_quiz["id"] != quiz["id"]
    assert delete_pictures(world, TEACHER, KID).json() == {"deleted": 0}                              # twice is fine
    never = world.store.add_member(world.a["id"], "newkid@school.test")
    assert delete_pictures(world, TEACHER, "newkid@school.test").json() == {"deleted": 0} and never is None      # never signed in: nothing handed in


def test_the_hourly_cleanup_starts_with_the_real_database_and_not_without(world, monkeypatch):
    from mathly2 import cleanup
    started = []

    def fake_start(store, backend, every=3600.0):
        import threading
        started.append((store, backend))
        return threading.Event()
    monkeypatch.setattr(cleanup, "start_hourly", fake_start)
    with TestClient(world.app):                                                                     # no Supabase: nothing starts
        pass
    assert started == []
    live = create_app(Settings(supabase_url="https://p.test", supabase_key="pub", supabase_secret="sec"), store=InMemoryStore(), authenticator=object())
    with TestClient(live):
        pass
    assert len(started) == 1 and started[0][0] is live.state.store and started[0][1] is live.state.pictures


def test_the_teachers_list_says_which_lessons_have_a_written_quiz_and_lists_the_classs_tests(world):
    test = world.store.create_test(world.a["id"], clock.school_day() + 10 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    got = world.get("/api/teaching/assignments", headers=auth(TEACHER)).json()[0]["class"]
    assert {l["id"]: l["has_quiz"] for l in got["lessons"]} == {world.quiz_lesson: True, world.plain_lesson: False}
    assert got["tests"] == [{"id": test["id"], "date": test["date"].isoformat(), "lessons": got["tests"][0]["lessons"]}] and got["tests"][0]["lessons"]


# --- work-tabs-and-hints 2.1: the numbers on the teacher's tabs ---

def counts(client, who=TEACHER):
    return client.get("/api/teaching/counts", headers=auth(who)).json()


def test_the_counts_are_classes_tests_assignments_and_submissions_waiting(world):
    assert counts(world) == {"classes": 1, "tests": 0, "assignments": 0, "inbox": 0}
    for _ in range(3):
        world.store.create_test(world.a["id"], clock.school_day() + 10 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    a = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    b = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    give(world, kind="quiz", quiz_lesson=world.quiz_lesson)
    exam = world.store.create_test(world.a["id"], clock.school_day() + 5 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    give(world, kind="exercise_test", test_id=exam["id"], exercise_number=1)
    submit(world, a["id"], KID)
    submit(world, a["id"], KID2)
    submit(world, b["id"], KID)
    assert counts(world) == {"classes": 1, "tests": 4, "assignments": 4, "inbox": 3}


def test_checking_a_submission_lowers_the_inbox_and_removed_items_are_not_counted(world):
    a = give(world, kind="quiz", quiz_lesson=world.quiz_lesson).json()
    test = world.store.create_test(world.a["id"], clock.school_day() + 10 * DAY, [world.quiz_lesson], TEACHER, created_at=clock.now())
    sub = submit(world, a["id"], KID)
    assert counts(world)["inbox"] == 1
    world.post(f"/api/submissions/{sub['id']}/grade", json={"grade": 80, "seen": sub["handed_at"].isoformat()}, headers=auth(TEACHER))
    assert counts(world)["inbox"] == 0
    world.store.remove_test(test["id"])
    world.delete(f"/api/assignments/{a['id']}", headers=auth(TEACHER))
    assert counts(world) == {"classes": 1, "tests": 0, "assignments": 0, "inbox": 0}


def test_another_teachers_items_are_not_counted_and_a_developer_counts_everything(world):
    give(world, kind="quiz", quiz_lesson=world.quiz_lesson)
    world.store.create_test(world.b["id"], clock.school_day() + 10 * DAY, [world.other_quiz], OTHER_TEACHER, created_at=clock.now())
    assert counts(world, OTHER_TEACHER) == {"classes": 1, "tests": 1, "assignments": 0, "inbox": 0}
    assert counts(world) == {"classes": 1, "tests": 0, "assignments": 1, "inbox": 0}
    assert counts(world, DEV) == {"classes": 2, "tests": 1, "assignments": 1, "inbox": 0}
    assert world.get("/api/teaching/counts", headers=auth(KID)).status_code == 403
