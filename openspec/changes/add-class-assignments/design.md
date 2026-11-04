# Design

## Context

- Classes live in Supabase `classes` (`emails`, `teachers`, `lessons`, `exams` jsonb, `nicknames`), loaded and cached by `app/auth.py` `classes()`. The class exam board is a jsonb column edited by managers.
- Skill completion is in the student's progress (`P.done`), practice exams in `P.quizzes[] {at, n, right, ms, units}`, and unit-quiz sittings on the server after `add-server-quiz-grades`.
- The class report already loads every student's progress, so it can compute completion for each student in the page.

## Goals / Non-Goals

**Goals:**
- Assignments stored on the server per class, editable by the class teacher.
- Completion computed from data that already exists, with no new student-side writes.

**Non-Goals:**
- Push notifications for new assignments (the existing push in `app/push.py` is scoped to scan requests; a later change can generalize it).
- Assigning to individual students or groups (whole class only for now).
- Grades for assignments.

## Decisions

**Own table, not a jsonb column on `classes`.** `math_assignments(id uuid, class_id int references classes on delete cascade, title, note, due_on date, items jsonb, created_by_email, created_at, updated_at)`. A table keeps edits by the class teacher separate from the manager-owned class row (`save_class` rewrites the whole row) and allows per-assignment timestamps. Alternative considered: `classes.assignments` jsonb like `exams`. Rejected because concurrent edits by the manager and the teacher would overwrite each other.

**Items format.** `[{kind:"skill", id}, {kind:"unit_quiz", unit}, {kind:"exam", units:[...]}]`, validated on the server against `app/math_algebra9.json` and the class's `lessons`. At most 20 items.

**Routes (`app/assignments.py`).**
- Teacher: `GET/POST /api/classes/{id}/assignments`, `PUT/DELETE /api/classes/{id}/assignments/{aid}`. The rule: the email is in the class's `teachers`, or the account has `management.access` (same as the class report).
- Student: `GET /api/math/assignments` returns the assignments of all the student's classes with `due_on` in the last 14 days or later, plus the student's unit-quiz sitting times (from `math_quiz_sittings`) so the page can decide unit-quiz completion without another call.

**Completion computed in the page.** One pure function `assignmentState(assignment, progress, sittings, now)` is used on the student's home and in the report, so both always agree. Due date is the end of `due_on` in Asia/Jerusalem. "Done late" uses the item's completion time where one exists (`P.done[id]`, sitting `submitted_at`, exam `at`).

**Report.** The report endpoint adds `assignments` for the class and each student's `quiz_sittings` (already added by `add-server-quiz-grades`). The "needs attention" signal list from `add-class-attention-view` gets one more signal fed by `assignmentState`.

## Risks / Trade-offs

- [Skill completion is device-reported] → Same trust level as the rest of the practice data, and labelled as such in the report.
- [A teacher deletes an assignment students were working on] → The form asks for confirmation and states how many students already started it.
- [Time zone at the due-date boundary] → Due dates are dates, and late means after 23:59 Jerusalem time on that date.

## Migration Plan

1. Apply the additive migration.
2. Deploy. Without the table, the routes return 503 `assignments_unavailable`, the student card is hidden and the report tab says assignments are unavailable.
3. Rollback: previous code. The table can stay.
