# Tasks

## 1. Storage

- [x] 1.1 Add migration `<ts>_math_worksheets.sql`: `math_worksheets`, `math_worksheet_submissions` (cascade from class and worksheet, unique per worksheet and student, score 0–100, comment ≤1000), service-only grants, private bucket `mathly-worksheets` (JPEG and PDF, 10 MB) with a restrictive policy. Verify it applies on the local test database (pgserver) and that deleting a class removes its worksheets and submissions.
- [x] 1.2 Add `pypdfium2` to `requirements.txt`. Verify `pip install -r requirements.txt` works and a 2-page test PDF renders to 2 JPEGs.

## 2. Server

- [x] 2.1 Add `app/worksheets.py` with the storage adapter (rows and bucket through the service key, 503 `worksheets_unavailable` when missing) and file checks: PDF (header, ≤10 MB, ≤10 pages, render with time limit) and photos through `clean_image`. Verify in `tests/test_worksheets.py`: valid PDF, 11-page PDF, oversized file, non-PDF with a .pdf name, 1 and 11 photos.
- [x] 2.2 Add the teacher upload route `POST /api/classes/{cid}/worksheets` with the class-teacher-or-manager rule. Verify: class teacher 201, other teacher 403, student 403, response has no storage paths.
- [x] 2.3 Accept `{kind: "worksheet", id}` in `clean_assignment` (same class, at most 5), and delete worksheets (rows, submissions, files) dropped by an assignment update or delete. Verify in `tests/test_assignments.py`: worksheet of another class rejected, 6 worksheets rejected, worksheet-only assignment accepted, removing the item deletes the worksheet and its submissions.
- [x] 2.4 Add the page and original routes for class members and the class teacher. Verify: a class student reads pages and the PDF, a student of another class gets 404, the original of a photo worksheet is 404.
- [x] 2.5 Add the student hand-in route (create or replace, 409 `already_checked` after a check) and the route to read their own pages. Verify: hand in, replace before check keeps only the new pages and removes the old files, replace after check refused, another student's pages 404, student outside the class 404.
- [x] 2.6 Add the teacher's submission page route and the check route (`score` 0–100 or empty, `comment` ≤1000, `checked_at` set once). Verify: check, change later keeps the first `checked_at`, score 120 rejected, other teacher 403.
- [x] 2.7 Add `worksheets` and the student's `submissions` to `GET /api/math/assignments`, and the class's worksheets and each student's `worksheet_submissions` to the class report. Verify both answers in tests, with `null` when the tables are missing and no storage paths ever.
- [x] 2.8 Record `worksheet_added`, `worksheet_submitted`, `worksheet_checked` in the actions log. Verify in `tests/test_monitoring.py`.
- [x] 2.9 Extend the hourly cleanup (`app/answer_cleanup.py`) to delete worksheets that no assignment uses after 24 hours, with their files. Verify with a test that an unused 25-hour-old worksheet is removed and a used one or a 1-hour-old one is kept.

## 3. Completion

- [x] 3.1 Extend `assignmentState` in `static/math-sky.js` to take `{sittings, submissions}` (a bare array still read as sittings) and handle worksheet items (done at `submitted_at`, late after the Jerusalem end of the due date, not known when submissions are null). Update the three callers. Verify in `tests/test_sky_browser.py` with the spec's scenarios (on time at 22:00 on the due date, late, not handed in) and that existing assignment tests still pass.

## 4. Teacher UI

- [x] 4.1 Add the worksheet option to the assignment form: title, choose a PDF or photos, upload progress, page count, remove; hidden when worksheets are unavailable. Removing a worksheet, or deleting the assignment, confirms with the number of students who handed in. Verify with a browser test that uploads a PDF, saves, and removes it with the confirmation.
- [x] 4.2 In the report's "משימות" tab, show per worksheet: handed in, late, missing, waiting for a check; and per student a button that opens the submission (pages, score field, comment, save). Verify with a browser test on a 3-student fixture: open, check with a score and comment, counts update.

## 5. Student UI

- [x] 5.1 Show worksheet items on the "משימות מהמורה" card, with a viewer (pages one under the other, download button). The continue button opens the viewer for a worksheet item. Verify with a browser test.
- [x] 5.2 Add the hand-in sheet (take or choose 1–10 photos, reorder or remove, send with progress, keep photos on failure, replace before check) and show "הוגש", "נבדק", the score and the comment on the card. Verify with a browser test: hand in, replace, and see a check from a fixture.
- [x] 5.3 Styles in `static/math.css` for the form, viewer, hand-in sheet and report, in light and dark and at phone width. Verify by screenshot in the browser tests at 390 px.

## 6. Docs and integration

- [x] 6.1 Update `static/guide.js` (student: opening a worksheet and handing in; teacher: attaching a worksheet and checking) and `README.md` (feature, limits, migration, `pypdfium2`). Verify `tests/test_guide_browser.py` passes.
- [x] 6.2 Run the full `pytest` suite and check locally end to end: the teacher attaches a PDF to an assignment, a student opens it and hands in 2 photos, the teacher checks with a score and comment, and the student sees it.
