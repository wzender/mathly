# Proposal

## Why

Assignments (`add-class-assignments`) can only point at practice that already exists in the app: a skill, a unit quiz or a practice exam. Most homework is still a worksheet the teacher wrote or photocopied, handed out on paper or in a WhatsApp group, and collected in class. The teacher cannot give it through Mathly, and cannot see in the משימות tab who handed it in. Letting the teacher attach a worksheet to an assignment, and letting students hand in a photo of their solution, brings that homework into the same place.

## What Changes

- New assignment item kind: **worksheet (דף עבודה)**. In the assignment form the class teacher (or a manager) uploads a PDF (up to 10 pages) or 1 to 10 photos, with a short title. An assignment can have up to 5 worksheets next to its other items.
- A PDF is turned into page images on the server, so every phone shows it the same way. The original PDF is kept so it can be downloaded and printed.
- Students open the worksheet from the **"משימות מהמורה"** card: its pages are shown one under the other, with a button to download the original.
- Students **hand in** their solution as 1 to 10 photos. Until the teacher checks it, the student can replace the submission. After the due date, a submission is still accepted and marked late.
- A worksheet item is **done** when the student has handed in. It is late when handed in after the Jerusalem end of the due date (same rule as the other items).
- In the class report's **"משימות"** tab, the teacher sees for each worksheet who handed in, who is late and who is missing, and how many submissions are waiting to be checked. The teacher opens a submission, sees its pages, and marks it **checked**, with an optional score (0–100) and an optional comment.
- The student sees the check on the assignment card: "נבדק", the score and the comment. A checked submission can no longer be replaced.
- No AI check of worksheets.
- The user guide (both tabs) and README describe the feature.

## Capabilities

### New Capabilities

- `assignment-worksheets`: worksheets a class teacher attaches to an assignment, how students open them and hand in a solution, and how the teacher checks submissions.

### Modified Capabilities

(none: there are no main specs yet. `class-assignments` is still an open change. The new item kind and its completion rule are specified in this capability.)

## Impact

- New migration `<ts>_math_worksheets.sql`: tables `math_worksheets` and `math_worksheet_submissions` (service-only, deleted with their class), and a private storage bucket `mathly-worksheets`.
- New module `app/worksheets.py`: upload, read and delete routes for the teacher, read and hand-in routes for students, the check route, and cleanup of worksheets that no assignment uses.
- `app/assignments.py`: `clean_assignment` accepts `{kind: "worksheet", id}` items that belong to the class. Deleting an assignment, or removing a worksheet from it, removes the worksheet and its submissions.
- `app/class_report.py` and `GET /api/math/assignments`: return worksheet submissions (status, times, score, comment), but not storage paths.
- `static/math-sky.js` `assignmentState`: the worksheet item. `static/math.js`: upload in the assignment form, worksheet viewer, hand-in sheet, submission review in the report. `static/math.css`, `static/guide.js`, `README.md`.
- New dependency `pypdfium2` (PDF to page images, self-contained wheel).
- `app/answer_cleanup.py` (hourly job): also removes worksheets that no assignment uses after 24 hours.
- Tests: new `tests/test_worksheets.py`, browser tests for the teacher and student flows, `tests/test_sky_browser.py` for the completion rule.
- Depends on `add-class-assignments` (in place).
