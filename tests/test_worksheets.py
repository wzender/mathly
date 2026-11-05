"""Worksheets on assignments: the teacher uploads, the class reads, students hand in, the teacher checks.
Storage is in memory; the migration runs on real PostgreSQL."""
import asyncio
import io
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.worksheets import Worksheets, WorksheetsUnavailable, cleanup_unused, render_pdf
from scan_support import BOOTSTRAP, postgres_server  # noqa: F401  (a fixture)
from app.answer_scans import ScanError
from app.main import create_app
from test_assignments import (EMAILS, GOOD, MANAGER, OTHER_TEACHER, OUTSIDER, PUPIL4, STUDENT, TEACHER, ClassAuth,
                              MemoryAssignments, client)

MIGRATION = Path("supabase/migrations/20261105090000_math_worksheets.sql")


class ReportAuth(ClassAuth):
    """Enough of Supabase for the class report: the accounts of the class, and no saved progress."""

    def user_accounts(self, emails):
        return {email: {"id": uid, "name": ""} for uid, email in EMAILS.items() if email in emails}

    def _admin(self, path, method="GET", body=None, prefer=""):
        return []


def pdf(pages=2, extra=b""):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(595, 842)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue() + extra


def photo(color="white", size=(300, 400), fmt="PNG"):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, fmt)
    return out.getvalue()


class MemoryWorksheets(Worksheets):
    configured = True

    def __init__(self):
        self.rows, self.subs, self.files, self.fail = {}, {}, {}, False

    def _check(self):
        if self.fail:
            raise WorksheetsUnavailable("worksheets_unavailable")

    def add(self, row):
        self._check()
        row = {"created_at": datetime.now(timezone.utc).isoformat(), **row}
        self.rows[row["id"]] = row
        return row

    def get(self, wid):
        self._check()
        return self.rows.get(wid)

    def of_class(self, class_id):
        self._check()
        return [r for r in self.rows.values() if r["class_id"] == class_id]

    def by_ids(self, ids):
        self._check()
        return [self.rows[i] for i in sorted(set(ids)) if i in self.rows]

    def older_than(self, cutoff):
        self._check()
        return [r for r in self.rows.values() if datetime.fromisoformat(r["created_at"]) < cutoff]

    def remove(self, wid):
        self._check()
        self.rows.pop(wid, None)
        self.subs = {k: s for k, s in self.subs.items() if s["worksheet_id"] != wid}   # cascade

    def submissions(self, wids, student_id=None):
        self._check()
        return [s for s in self.subs.values() if s["worksheet_id"] in wids and (student_id is None or s["student_id"] == student_id)]

    def submission(self, sid):
        self._check()
        return self.subs.get(sid)

    def save_submission(self, row):
        self._check()
        old = next((s for s in self.subs.values() if s["worksheet_id"] == row["worksheet_id"] and s["student_id"] == row["student_id"]), None)
        saved = {"checked_at": None, "score": None, "comment": "", **(old or {"id": str(uuid.uuid4())}), **row}
        self.subs[saved["id"]] = saved
        return saved

    def check(self, sid, fields):
        self._check()
        if sid not in self.subs:
            return None
        self.subs[sid] = {**self.subs[sid], **fields}
        return self.subs[sid]

    def put(self, key, data, content_type="image/jpeg"):
        self._check()
        self.files[key] = (data, content_type)

    def read(self, key):
        self._check()
        return self.files[key][0]

    def delete(self, keys):
        self._check()
        for k in keys:
            self.files.pop(k, None)


class NoAnswers:
    """No quiz sittings or review requests here: the report shows them as not read."""
    configured = True

    def quiz(self, *args, **kwargs):
        raise ScanError(503, "not_here")

    review = quiz


def setup(store=None):
    app = create_app(auth=ReportAuth())
    app.state.assignments, app.state.answers = MemoryAssignments(), NoAnswers()
    app.state.worksheets = store or MemoryWorksheets()
    return app


async def upload(c, class_id=3, title="דף עבודה – פיתגורס", files=None):
    files = files if files is not None else [("files", ("sheet.pdf", pdf(3), "application/pdf"))]
    return await c.post(f"/api/classes/{class_id}/worksheets", data={"title": title}, files=files)


async def assign(c, wid, class_id=3, **extra):
    body = {**GOOD, "items": [{"kind": "worksheet", "id": wid}], **extra}
    return await c.post(f"/api/classes/{class_id}/assignments", json=body)


def photos(n, name="p"):
    return [("files", (f"{name}{i}.jpg", photo(fmt="JPEG"), "image/jpeg")) for i in range(n)]


# ---- files in
def test_a_pdf_is_rendered_to_pages_and_bad_files_are_refused():
    pages = render_pdf(pdf(2))
    assert len(pages) == 2 and all(p.startswith(b"\xff\xd8") for p in pages)
    with Image.open(io.BytesIO(pages[0])) as first:
        assert first.width <= 1600 and first.height <= 2400 and first.format == "JPEG"
    for data, code in ((pdf(11), "too_many_pages"), (b"%PDF-1.7 not really", "unreadable_pdf"),
                       (photo(), "not_a_pdf"), (b"%PDF-" + b"0" * 10_000_001, "pdf_too_large")):
        with pytest.raises(Exception) as info:
            render_pdf(data)
        assert info.value.detail == code, code


def test_the_class_teacher_uploads_a_pdf_or_photos():
    store = MemoryWorksheets()
    app = setup(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            r = await upload(teacher)
            assert r.status_code == 201, r.text
            got = r.json()
            assert (got["title"], got["pages"], got["source"], got["class_id"]) == ("דף עבודה – פיתגורס", 3, "pdf", 3)
            assert "key" not in r.text and "w/" not in r.text   # no storage paths
            row = store.rows[got["id"]]
            assert row["original_key"].endswith("original.pdf") and store.files[row["original_key"]][1] == "application/pdf"
            assert len(row["page_keys"]) == 3 and all(k in store.files for k in row["page_keys"])
            # photos, in the order chosen
            colors = [("a.png", photo("red"), "image/png"), ("b.webp", photo("blue", fmt="WEBP"), "image/webp")]
            r = await upload(teacher, title="שני", files=[("files", f) for f in colors])
            assert r.status_code == 201 and (r.json()["pages"], r.json()["source"]) == (2, "images")
            first = store.files[store.rows[r.json()["id"]]["page_keys"][0]][0]
            with Image.open(io.BytesIO(first)) as im:
                assert im.getpixel((5, 5))[0] > 200 and im.getpixel((5, 5))[2] < 60   # red first
            count = len(store.rows)
            for files, title, status in (
                    ([("files", ("x.pdf", pdf(11), "application/pdf"))], "ok", 400),
                    ([("files", ("x.pdf", b"hello", "application/pdf"))], "ok", 415),       # not a PDF, PDF name
                    ([("files", ("x.txt", b"hello", "text/plain"))], "ok", 415),
                    (photos(11), "ok", 400),
                    ([("files", ("x.pdf", pdf(1), "application/pdf"))] + photos(1), "ok", 400),   # a PDF and photos
                    (photos(1), "", 400), (photos(1), "א" * 81, 400)):
                r = await upload(teacher, title=title, files=files)
                assert r.status_code == status, (title, r.text)
            assert len(store.rows) == count and len(store.files) == 3 + 1 + 2   # nothing more was stored
    asyncio.run(check())
    assert [a["kind"] for a in app.state.actions.recent()].count("worksheet_added") == 2


def test_only_the_class_teacher_or_a_manager_uploads():
    app = setup()

    async def check():
        for who in (STUDENT, OTHER_TEACHER, OUTSIDER):
            async with client(app, who) as c:
                assert (await upload(c)).status_code == 403, who
        async with client(app, MANAGER) as manager:
            assert (await upload(manager)).status_code == 201
            assert (await upload(manager, class_id=99)).status_code == 404
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as guest:
            assert (await upload(guest)).status_code == 401
    asyncio.run(check())


# ---- worksheets on assignments
def test_assignments_take_their_classs_worksheets_and_drop_the_ones_they_lose():
    store = MemoryWorksheets()
    app = setup(store)

    async def check():
        async with client(app, TEACHER) as teacher, client(app, OTHER_TEACHER) as other:
            mine = [(await upload(teacher, title=f"דף {i}")).json()["id"] for i in range(6)]
            theirs = (await upload(other, class_id=4)).json()["id"]
            assert (await assign(teacher, theirs)).status_code == 400                      # another class's worksheet
            assert (await assign(teacher, str(uuid.uuid4()))).status_code == 400
            many = [(await upload(teacher, title=f"עוד {i}")).json()["id"] for i in range(6)]
            six = {**GOOD, "items": [{"kind": "worksheet", "id": w} for w in many]}
            assert (await teacher.post("/api/classes/3/assignments", json=six)).status_code == 201   # no cap of 5 any more
            made = await assign(teacher, mine[0])                                         # a worksheet alone is fine
            assert made.status_code == 201 and made.json()["items"] == [{"kind": "worksheet", "id": mine[0]}]
            aid = made.json()["id"]
            both = {**GOOD, "items": [{"kind": "worksheet", "id": mine[0]}, {"kind": "worksheet", "id": mine[1]}]}
            assert (await teacher.put(f"/api/classes/3/assignments/{aid}", json=both)).status_code == 200
            # a student hands in the first; then the teacher removes it from the assignment
            async with client(app, STUDENT) as student:
                assert (await student.put(f"/api/math/worksheets/{mine[0]}/submission", files=photos(2))).status_code == 200
            keys = list(store.rows[mine[0]]["page_keys"]) + [store.rows[mine[0]]["original_key"]]
            sub_keys = [k for s in store.subs.values() for k in s["page_keys"]]
            only_second = {**GOOD, "items": [{"kind": "worksheet", "id": mine[1]}]}
            assert (await teacher.put(f"/api/classes/3/assignments/{aid}", json=only_second)).status_code == 200
            assert mine[0] not in store.rows and not store.subs
            assert not any(k in store.files for k in keys + sub_keys)
            # deleting the assignment takes its worksheets too
            assert (await teacher.delete(f"/api/classes/3/assignments/{aid}")).status_code == 200
            assert mine[1] not in store.rows
            # an upload not saved into an assignment can be taken back; one in use cannot
            assert (await teacher.delete(f"/api/classes/3/worksheets/{mine[2]}")).status_code == 200
            assert mine[2] not in store.rows
            await assign(teacher, mine[3])
            assert (await teacher.delete(f"/api/classes/3/worksheets/{mine[3]}")).status_code == 409
            assert (await other.delete(f"/api/classes/4/worksheets/{mine[4]}")).status_code == 404
    asyncio.run(check())


def test_without_the_worksheet_tables_assignments_still_work():
    store = MemoryWorksheets()
    app = setup(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            wid = (await upload(teacher)).json()["id"]
            await assign(teacher, wid)
            store.fail = True
            assert (await upload(teacher)).status_code == 503
            assert (await assign(teacher, wid)).status_code == 503
        async with client(app, MANAGER) as manager:   # skills and quizzes: a manager's assignment
            assert (await manager.post("/api/classes/3/assignments", json=GOOD)).status_code == 201
        async with client(app, TEACHER) as teacher:
            report = (await teacher.get("/api/classes/3/report")).json()
            assert report["worksheets"] is None and report["students"][0]["worksheet_submissions"] is None
        async with client(app, STUDENT) as student:
            data = (await student.get("/api/math/assignments")).json()
            assert len(data["assignments"]) == 2 and data["worksheets"] is None and data["submissions"] is None
            assert (await student.get(f"/api/math/worksheets/{wid}/pages/1")).status_code == 503
    asyncio.run(check())


# ---- the class reads it
def test_the_class_reads_the_worksheet_and_nobody_else_does():
    store = MemoryWorksheets()
    app = setup(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            wid = (await upload(teacher)).json()["id"]
            pics = (await upload(teacher, title="תמונות", files=photos(1))).json()["id"]
        for who in (STUDENT, TEACHER, MANAGER):
            async with client(app, who) as c:
                page = await c.get(f"/api/math/worksheets/{wid}/pages/3")
                assert page.status_code == 200 and page.headers["content-type"] == "image/jpeg", who
                assert page.headers["cache-control"].startswith("private")
                original = await c.get(f"/api/math/worksheets/{wid}/original")
                assert original.status_code == 200 and original.content.startswith(b"%PDF-")
                assert original.headers["content-type"] == "application/pdf"
                assert "attachment" in original.headers["content-disposition"]
        async with client(app, STUDENT) as student:
            assert (await student.get(f"/api/math/worksheets/{wid}/pages/4")).status_code == 404
            assert (await student.get(f"/api/math/worksheets/{wid}/pages/0")).status_code == 404
            assert (await student.get(f"/api/math/worksheets/{pics}/original")).status_code == 404    # photos: no PDF
            assert (await student.get("/api/math/worksheets/not-a-uuid/pages/1")).status_code == 404
        for who in (PUPIL4, OTHER_TEACHER, OUTSIDER):
            async with client(app, who) as c:
                assert (await c.get(f"/api/math/worksheets/{wid}/pages/1")).status_code in (403, 404), who
                assert (await c.get(f"/api/math/worksheets/{wid}/original")).status_code in (403, 404), who
    asyncio.run(check())


# ---- students hand in, the teacher checks
def test_a_student_hands_in_replaces_and_is_checked():
    store = MemoryWorksheets()
    app = setup(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            wid = (await upload(teacher)).json()["id"]
            loose = (await upload(teacher, title="לא במשימה")).json()["id"]
            await assign(teacher, wid)
        async with client(app, STUDENT) as student:
            first = await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(2))
            assert first.status_code == 200, first.text
            got = first.json()
            assert (got["pages"], got["checked_at"], got["score"]) == (2, None, None) and "page_keys" not in got
            old_keys = list(store.subs[got["id"]]["page_keys"])
            again = await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(3, "q"))
            assert again.status_code == 200 and again.json()["id"] == got["id"] and again.json()["pages"] == 3
            assert again.json()["submitted_at"] >= got["submitted_at"]
            assert len(store.subs) == 1 and not any(k in store.files for k in old_keys)   # only the new set is kept
            assert (await student.get(f"/api/math/worksheets/{wid}/submission/pages/3")).status_code == 200
            assert (await student.get(f"/api/math/worksheets/{wid}/submission/pages/4")).status_code == 404
            for files in ([], photos(11)):
                assert (await student.put(f"/api/math/worksheets/{wid}/submission", files=files or {"x": "y"})).status_code in (400, 422)
            assert (await student.put(f"/api/math/worksheets/{loose}/submission", files=photos(1))).status_code == 404
            mine = (await student.get("/api/math/assignments")).json()
            assert [w["id"] for w in mine["worksheets"]] == [wid] and mine["submissions"][0]["pages"] == 3
            assert "key" not in str(mine) and "teacher@x.test" not in str(mine)
        sid = got["id"]
        async with client(app, PUPIL4) as other, client(app, OUTSIDER) as outsider:
            assert (await other.put(f"/api/math/worksheets/{wid}/submission", files=photos(1))).status_code == 404
            assert (await other.get(f"/api/math/worksheets/{wid}/submission/pages/1")).status_code == 404
            assert (await outsider.put(f"/api/math/worksheets/{wid}/submission", files=photos(1))).status_code in (403, 404)
        async with client(app, TEACHER) as teacher:
            report = (await teacher.get("/api/classes/3/report")).json()
            assert [w["id"] for w in report["worksheets"]] == [wid, loose]
            (subs,) = [s["worksheet_submissions"] for s in report["students"] if s["email"] == EMAILS[STUDENT]]
            assert [(s["id"], s["pages"], s["checked_at"]) for s in subs] == [(sid, 3, None)]
            page = await teacher.get(f"/api/classes/3/worksheets/{wid}/submissions/{sid}/pages/1")
            assert page.status_code == 200 and page.headers["content-type"] == "image/jpeg"
            url = f"/api/classes/3/worksheets/{wid}/submissions/{sid}"
            for bad in ({"score": 120}, {"score": -1}, {"score": 8.5}, {"score": "85"}, {"score": True}, {"comment": "א" * 1001}):
                assert (await teacher.put(url, json=bad)).status_code == 400, bad
            checked = await teacher.put(url, json={"score": 85, "comment": " יפה, שימי לב ליחידות "})
            assert checked.status_code == 200
            first_check = checked.json()["checked_at"]
            assert (checked.json()["score"], checked.json()["comment"]) == (85, "יפה, שימי לב ליחידות") and first_check
            later = await teacher.put(url, json={"score": 90, "comment": ""})
            assert (later.json()["score"], later.json()["checked_at"]) == (90, first_check)   # first check time kept
            assert (await teacher.put(url, json={"score": None, "comment": ""})).json()["score"] is None   # no score
            await teacher.put(url, json={"score": 90, "comment": "יפה"})
        for who in (OTHER_TEACHER, STUDENT):
            async with client(app, who) as c:
                assert (await c.put(f"/api/classes/3/worksheets/{wid}/submissions/{sid}", json={"score": 1})).status_code == 403
                assert (await c.get(f"/api/classes/3/worksheets/{wid}/submissions/{sid}/pages/1")).status_code == 403
        async with client(app, STUDENT) as student:
            refused = await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(1))
            assert (refused.status_code, refused.json()["detail"]) == (409, "already_checked")
            assert store.subs[sid]["score"] == 90 and len(store.subs[sid]["page_keys"]) == 3   # as it was
            seen = (await student.get("/api/math/assignments")).json()["submissions"][0]
            assert (seen["score"], seen["comment"]) == (90, "יפה") and seen["checked_at"]
    asyncio.run(check())
    kinds = [a["kind"] for a in app.state.actions.recent(50)]
    assert kinds.count("worksheet_submitted") == 2 and kinds.count("worksheet_checked") == 4


def test_unused_worksheets_are_deleted_after_a_day():
    store, assignments = MemoryWorksheets(), MemoryAssignments()
    now = datetime.now(timezone.utc)
    old, fresh, used = (str(uuid.uuid4()) for _ in range(3))
    for wid, age in ((old, 25), (fresh, 1), (used, 25)):
        store.add({"id": wid, "class_id": 3, "title": "x", "source": "images", "pages": 1, "original_key": None,
                   "page_keys": [f"w/{wid}/1.jpg"], "byte_size": 1, "created_at": (now - timedelta(hours=age)).isoformat()})
        store.put(f"w/{wid}/1.jpg", b"x")
    assignments.add({**GOOD, "class_id": 3, "items": [{"kind": "worksheet", "id": used}]})
    assert cleanup_unused(store, assignments, now) == 1
    assert set(store.rows) == {fresh, used} and f"w/{old}/1.jpg" not in store.files


def test_the_migration_is_additive_service_only_and_follows_its_class(postgres_server):  # noqa: F811
    psycopg = pytest.importorskip("psycopg")
    database = "ws_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute("create database " + database)
    try:
        with psycopg.connect(postgres_server.get_uri(database=database), autocommit=True) as c:
            c.execute(BOOTSTRAP)
            c.execute("insert into classes values (2, 'other class')")
            c.execute(MIGRATION.read_text())
            assert c.execute("select allowed_mime_types, public from storage.buckets where id='mathly-worksheets'").fetchone() == (
                ["image/jpeg", "application/pdf"], False)
            c.execute("set role service_role")
            sheet = lambda cls, source="images", pages=1, keys=None, original=None, title="דף": c.execute(
                "insert into math_worksheets(class_id,title,source,pages,original_key,page_keys,byte_size) "
                "values(%s,%s,%s,%s,%s,%s,1) returning id", (cls, title, source, pages, original, keys or ["a"])).fetchone()[0]
            w1 = sheet(1, "pdf", 2, ["a", "b"], "o.pdf")
            w2 = sheet(2)
            for bad in (dict(cls=99), dict(cls=1, title=""), dict(cls=1, pages=2), dict(cls=1, source="pdf"),
                        dict(cls=1, original="o.pdf"), dict(cls=1, pages=11, keys=["k"] * 11), dict(cls=1, source="doc")):
                with pytest.raises(psycopg.errors.Error):
                    sheet(**bad)
            student = str(uuid.uuid4())
            hand = lambda w, keys=("p",), score=None, comment="": c.execute(
                "insert into math_worksheet_submissions(worksheet_id,student_id,page_keys,score,comment) values(%s,%s,%s,%s,%s)",
                (w, student, list(keys), score, comment))
            hand(w1)
            hand(w2, score=100)
            # a second one of the same student, an unknown worksheet, no pages, a score over 100
            for bad in (dict(w=w1), dict(w=str(uuid.uuid4())), dict(w=w1, keys=()), dict(w=w1, score=101)):
                with pytest.raises(psycopg.errors.Error):
                    hand(**bad)
            with pytest.raises(psycopg.errors.Error):
                c.execute("update math_worksheet_submissions set comment=%s", ("א" * 1001,))
            c.execute("reset role")
            c.execute("delete from classes where id = 1")   # the class takes its worksheets and their submissions with it
            assert c.execute("select count(*) from math_worksheets").fetchone()[0] == 1
            assert c.execute("select count(*) from math_worksheet_submissions").fetchone()[0] == 1
            c.execute("set role authenticated")
            for table in ("math_worksheets", "math_worksheet_submissions"):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    c.execute("select * from " + table)
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute("drop database " + database + " with (force)")


# ---- the AI's check of a submission: a suggestion for the teacher, one of their 3 requests a day
class Grader:
    def __init__(self, result=None, error=None):
        self.calls, self.result, self.error = [], result, error

    def grade(self, title, sheet_pages, solution_pages):
        self.calls.append((title, len(sheet_pages), len(solution_pages)))
        if self.error:
            raise self.error
        return self.result or {"readable": True, "score": 80, "comment": "יפה מאוד. תרגיל 3 דורש תיקון.", "usage": None}


def handed_in(app):
    """A worksheet in an assignment of class 3 with a 2-page submission by STUDENT; (worksheet id, submission id)."""
    async def go():
        async with client(app, TEACHER) as teacher:
            wid = (await upload(teacher)).json()["id"]
            await assign(teacher, wid)
        async with client(app, STUDENT) as student:
            return wid, (await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(2))).json()["id"]
    return asyncio.run(go())


def test_the_ai_check_suggests_a_score_and_comment_and_counts_toward_the_three(monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    app = setup()
    grader = app.state.homework_grader = Grader()
    wid, sid = handed_in(app)
    url = f"/api/classes/3/worksheets/{wid}/submissions/{sid}/ai-check"

    async def check():
        async with client(app, TEACHER) as teacher:
            r = await teacher.post(url)
            assert r.status_code == 200, r.text
            assert r.json() == {"score": 80, "comment": "יפה מאוד. תרגיל 3 דורש תיקון.", "readable": True, "left": 2}
            assert grader.calls == [("דף עבודה – פיתגורס", 3, 2)]                          # 3 sheet pages, 2 solution pages
            assert app.state.worksheets.subs[sid]["checked_at"] is None                    # a suggestion: nothing is saved
            for _ in range(2):
                assert (await teacher.post(url)).status_code == 200
            refused = await teacher.post(url)
            assert (refused.status_code, refused.json()["detail"]) == (429, "teacher_ai_limit")
            assert len(grader.calls) == 3
        for who in (STUDENT, OTHER_TEACHER):
            async with client(app, who) as c:
                assert (await c.post(url)).status_code == 403
        async with client(app, OTHER_TEACHER) as other:
            assert (await other.post(f"/api/classes/4/worksheets/{wid}/submissions/{sid}/ai-check")).status_code == 404
    asyncio.run(check())
    assert [a["kind"] for a in app.state.actions.recent(50)].count("worksheet_ai_checked") == 3


def test_a_failed_or_unreadable_ai_check_is_given_back(monkeypatch):
    from app.math_photo import PhotoUnavailable
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    app = setup()
    wid, sid = handed_in(app)
    url = f"/api/classes/3/worksheets/{wid}/submissions/{sid}/ai-check"

    async def check():
        async with client(app, TEACHER) as teacher:
            app.state.homework_grader = Grader(error=PhotoUnavailable("down", "provider_error", ""))
            r = await teacher.post(url)
            assert (r.status_code, r.json()["detail"]) == (503, "ai_check_failed|provider_error")
            app.state.homework_grader = Grader({"readable": False, "score": None, "comment": "צלמו שוב", "usage": None})
            r = await teacher.post(url)
            assert r.json() == {"score": None, "comment": "צלמו שוב", "readable": False, "left": 3}
            assert (await teacher.get("/api/me")).json()["ai_left"] == 3                   # none of the two counted
    asyncio.run(check())


def test_the_ai_check_stays_locked_with_open_ended_questions_and_needs_a_key(monkeypatch):
    monkeypatch.delenv("MATHLY_OPEN_ENDED_LOCKED", raising=False)
    app = setup()
    wid, sid = handed_in(app)
    url = f"/api/classes/3/worksheets/{wid}/submissions/{sid}/ai-check"

    async def check():
        async with client(app, TEACHER) as teacher:
            r = await teacher.post(url)
            assert (r.status_code, r.json()["detail"]) == (403, "open_ended_locked")
            monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
            monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
            monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
            r = await teacher.post(url)
            assert (r.status_code, r.json()["detail"]) == (503, "grading_unavailable")
            assert (await teacher.get("/api/me")).json()["ai_left"] == 3
    asyncio.run(check())


def test_the_homework_check_validates_what_the_ai_returns():
    from app.homework_grading import validate_check
    ok = validate_check({"readable": True, "score": 90, "comment": "  יפה  "})
    assert ok == {"readable": True, "score": 90, "comment": "יפה"}
    assert validate_check({"readable": False, "score": 0, "comment": "צלמו שוב"})["score"] is None   # unreadable: no score
    assert len(validate_check({"readable": True, "score": 1, "comment": "א" * 3000})["comment"]) == 1000
    for bad in ({"readable": True, "score": 101, "comment": "x"}, {"readable": True, "score": -1, "comment": "x"},
                {"readable": True, "score": 5.5, "comment": "x"}, {"readable": True, "score": 5, "comment": "  "},
                {"readable": "yes", "score": 5, "comment": "x"}, {"readable": True, "score": 5}, "text", None):
        with pytest.raises(Exception):
            validate_check(bad)


# ---- a page photographed by the phone (or this device) arrives like an exercise's answer
class AttemptAnswers(NoAnswers):
    def __init__(self):
        self.seen = []

    def action(self, user, action, **data):
        self.seen.append((user, action, data))
        return {"attempt": {"id": str(uuid.uuid4()), "question_id": data["question_id"], "snapshot": data["snapshot"]}}


def test_a_worksheet_page_can_be_photographed_like_an_answer():
    store, answers = MemoryWorksheets(), AttemptAnswers()
    app = setup(store)
    app.state.answers = answers

    async def check():
        async with client(app, TEACHER) as teacher:
            wid = (await upload(teacher)).json()["id"]
            loose = (await upload(teacher, title="לא במשימה")).json()["id"]
            await assign(teacher, wid)
        async with client(app, STUDENT) as student:
            got = await student.post("/api/math/worksheet-attempts", json={"worksheet_id": wid, "new": True})
            assert got.status_code == 200, got.text
            assert got.json()["attempt"]["question_id"] == f"worksheet:{wid}"
            assert "דף עבודה – פיתגורס" in got.json()["attempt"]["snapshot"]["question"]
            assert answers.seen[-1][2]["new"] is True
            # a worksheet no assignment of the student's class uses is not theirs to answer
            assert (await student.post("/api/math/worksheet-attempts", json={"worksheet_id": loose})).status_code == 404
            assert (await student.post("/api/math/worksheet-attempts", json={"worksheet_id": "nope"})).status_code == 404
        async with client(app, OUTSIDER) as outsider:
            assert (await outsider.post("/api/math/worksheet-attempts", json={"worksheet_id": wid})).status_code in (403, 404)
    asyncio.run(check())
