# Design

## Context

- Assignments live in `math_assignments` (`app/assignments.py`): `items` is a jsonb array validated by `clean_assignment` against the class's units, 1 to 20 items. The class teacher or a manager writes them (`class_row`); students read them through `GET /api/math/assignments`.
- Completion is not stored. `assignmentState(a, P, sittings, now)` in `static/math-sky.js` works it out from the progress and the unit-quiz sittings. It is called on the student's home, in the report tab, and in the "needs attention" signal.
- Images already have a safe path: `clean_image` in `app/answer_scans.py` checks type, size and pixel count, re-encodes to JPEG and drops metadata. `app/unit_resources.py` keeps teacher photos in a private Supabase bucket, read and written only with the service key, with a restrictive storage policy.
- Unreferenced answer images are removed by the hourly `python -m app.answer_cleanup`.
- There is no PDF handling in the project today.

## Goals / Non-Goals

**Goals:**
- A worksheet is just another assignment item, so the card, the report, the "needs attention" signal and the late rule all work for it without special cases.
- Every file goes through the server: no public URLs and no storage paths in the browser.
- The feature switches off cleanly when the migration is missing.

**Non-Goals:**
- AI checking of worksheets.
- Writing on the worksheet in the app (annotating the PDF). Students solve on paper and photograph.
- Teacher annotations on the submission photos. The teacher gives a score and a comment only.
- Returning a checked submission for another try. A later change can add "return for correction".
- Push notifications for new worksheets or checks.
- Reusing a worksheet across classes or assignments. Each upload belongs to one class.

## Decisions

**Item format: `{kind: "worksheet", id}`.** The id points to a row of `math_worksheets`. `clean_assignment` gets the class's worksheet ids and accepts a worksheet item only when its id belongs to the same class. At most 5 worksheet items per assignment, within the existing 20-item limit. An assignment can be only a worksheet. Alternative considered: a separate `worksheets` list next to `items`. Rejected because then every consumer of `items` (the card, the report, the continue button, the attention signal) would need a second path.

**Upload first, then save the assignment.** `POST /api/classes/{class_id}/worksheets` (multipart: title, files) stores the worksheet with `class_id` and returns `{id, title, pages}`. The form then saves the assignment with the item. A worksheet that no assignment uses for 24 hours is deleted by the hourly cleanup, the same idea as orphan answer images. Alternative considered: upload into an existing assignment (`/assignments/{aid}/worksheets`). Rejected because a new assignment has no id until it is saved, and the form would need two saves.

**Removing a worksheet.** When an assignment update drops a worksheet item, or the assignment is deleted, the server deletes the worksheet row, its submissions (cascade) and their files. The form shows the number of submissions in its confirmation, from the report data it already has.

**Tables (migration `<ts>_math_worksheets.sql`).**
- `math_worksheets(id uuid, class_id bigint references classes on delete cascade, title text ≤80, source text check in ('pdf','images'), pages int 1..10, original_key text null, page_keys text[], byte_size int, created_by_email, created_at)`.
- `math_worksheet_submissions(id uuid, worksheet_id uuid references math_worksheets on delete cascade, student_id uuid, student_email text, page_keys text[] 1..10, submitted_at timestamptz, checked_at timestamptz null, score int null check 0..100, comment text ≤1000 default '', checked_by_email text default '', unique(worksheet_id, student_id))`.
- Both service-only (RLS on, all grants revoked from anon/authenticated), like `math_assignments`.
- Bucket `mathly-worksheets`: private, `image/jpeg` and `application/pdf`, 10 MB limit, with a restrictive policy like `mathly-resources`. Keys: `w/<worksheet id>/<n>.jpg`, `w/<worksheet id>/original.pdf`, `s/<worksheet id>/<student id>/<random>/<n>.jpg`.

**PDF pages rendered on the server with `pypdfium2`.** Phones do not show PDFs inline the same way: Android Chrome downloads them. The server checks the file (starts with `%PDF-`, ≤10 MB, opens, ≤10 pages), renders each page to JPEG at about 1600 px wide, and stores the pages and the original. Rendering runs in the thread pool, with a time limit per page. `pypdfium2` ships a self-contained PDFium wheel, so no system packages are needed on the Space. Alternatives considered: `pdf.js` in the browser (a large vendored library and more work per phone), or PDF only through download (poor on phones).

**Photos reuse `clean_image`.** Teacher photos and student submissions go through `clean_image` (5 MB, JPEG/PNG/WebP, re-encoded, metadata dropped). The student's phone sends the photos as they are. The hand-in sheet reuses the camera/file picker of the open-answer flow (`static/answer-scans.js`), without its AI step.

**Routes (`app/worksheets.py`).**
- Teacher (class teacher or manager, same `class_row` rule): `POST /api/classes/{cid}/worksheets`; `GET /api/classes/{cid}/worksheets/{wid}/submissions/{sid}/pages/{n}`; `PUT /api/classes/{cid}/worksheets/{wid}/submissions/{sid}` with `{score, comment}` (sets `checked_at` the first time, keeps it after that).
- Class members and the class teacher: `GET /api/math/worksheets/{wid}/pages/{n}` (JPEG) and `GET /api/math/worksheets/{wid}/original` (PDF worksheets only; for a photo worksheet the download button saves the page images one by one). The worksheet's class must be one of the account's classes, or the account its teacher or a manager; otherwise 404.
- Student: `PUT /api/math/worksheets/{wid}/submission` (multipart files) creates or replaces their submission, refused with 409 `already_checked` after a check; `GET /api/math/worksheets/{wid}/submission/pages/{n}` reads their own pages.
- Pages are served with `Cache-Control: private, max-age=3600`.

**Data for the page.** `GET /api/math/assignments` adds `worksheets` (`{id, title, pages, source}` for the worksheets in the returned assignments) and `submissions` (the student's own: `{worksheet_id, pages, submitted_at, checked_at, score, comment}`). The report adds the same per student (`worksheet_submissions`) and the worksheets of the class.

**Completion.** `assignmentState(a, P, server, now)`: the third argument becomes `{sittings, submissions}`. A bare array is still read as `sittings`, so a caller that was not updated keeps working. A worksheet item is done at its submission's `submitted_at`; `known` is false when `submissions` is null (the server could not read them), as for unit quizzes. The three callers pass the new object.

**Actions log.** `worksheet_added`, `worksheet_submitted`, `worksheet_checked` go to the monitoring feed (`app/monitoring.py` `MON_ACTIONS`), like the assignment actions.

**Unavailable.** If the tables or bucket are missing, worksheet routes answer 503 `worksheets_unavailable`. The class report and `/api/math/assignments` return `worksheets: null`; the form hides the worksheet option, and a worksheet item whose data is missing shows as "דף העבודה לא זמין" and counts as not known.

## Risks / Trade-offs

- [Parsing untrusted PDFs] → Only class teachers and managers can upload; size, page and time limits; PDFium is maintained and fuzzed. The rendered JPEGs are what students see; the original is only downloaded.
- [Storage and egress] → Up to 10 pages per submission, re-encoded to ≤2400 px JPEG (~300–600 KB). A class of 30 with 5 worksheets a month is in the low GB per year. If egress becomes a concern, submissions can move to the Hugging Face bucket used for answers (`MATHLY_ANSWER_BUCKET`) in a later change.
- [Large uploads on weak phone connections] → The hand-in sheet shows progress, keeps the chosen photos when sending fails, and lets the student try again.
- [Teacher removes a worksheet students already handed in] → Confirmation names the number of submissions.
- [Students cannot fix a checked submission] → Deliberate for now (see Non-Goals). The teacher can still change the score and comment.

## Migration Plan

1. Add `pypdfium2` to `requirements.txt`.
2. Apply the additive migration (two tables and the bucket).
3. Deploy. Without the migration, worksheets are switched off and assignments work as before.
4. Rollback: previous code. The tables and bucket can stay; old code never reads worksheet items, but it would reject saving an assignment that has one (unknown item kind), so teachers should not edit those assignments until the code is back.
