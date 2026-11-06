# Design

## Context

See proposal.md for the motivation. The facts that shape the approach:

- **Main specs are empty.** All current behaviour lives in unarchived changes (`add-class-assignments`, `add-assignment-worksheets`, `add-server-quiz-grades`, `add-teacher-grade-review`, `add-class-attention-view`, `add-misconception-patterns`, `add-open-question-phone-scan`). Several are still marked in progress.
- **Unit-quiz sittings** (`math_quiz_sittings`) store `unit_id`, `attempt_ids`, `submitted_at`, `time_up`, `client_key`. The start time and the time limit live only in the student's page (`P.uq[unit].sitting.started`, `static/math.js`). Any number of sittings is allowed; the report shows the latest.
- **Grades** come from `app/quiz_grades.py` (`sitting_view`), with teacher reviews taking precedence over AI scores. Quiz questions have `points` and `question` and no skill tags.
- **Assignments** (`math_assignments`) are class-wide, with `items` as JSON. `worksheets_only()` in `app/assignments.py` limits non-managers to worksheet items.
- **Worksheet submissions** (`math_worksheet_submissions`) are unique per `(worksheet_id, student_id)` and are replaced in place until `checked_at` is set; then they are frozen. The AI check (`app/homework_grading.py`) is called one submission at a time by the teacher and only fills the review form.
- **AI queue** (`app/ai_queue.py`, `math_ai_requests`): students never call the AI; each pending `grading` request is sent one by one by the class teacher, and each send uses `TeacherQuota` (`app/teacher_ai.py`, 3/day, in memory).
- **Phone scans** (`math_answer_scans`) are bound to one `math_question_attempts` row and one attachment (one image).
- **Misconceptions, skill states, fading, examples** are computed in the browser from the progress each device uploads (`math_progress`); the class report reuses the same code (`Sky.patterns`, `Sky.assignmentState`).
- **Exam board**: `classes.exams` is a JSON array of `{subject, date}`.

## Goals / Non-Goals

**Goals:**
- Reuse what exists (states, `Sky.*` helpers, the queue, the phone flow, `sitting_view`) instead of adding parallel systems.
- Server-trusted where it matters for grades: final-quiz start time, attempt count, official grade, release.
- Every new table follows the existing pattern: service-role only, RLS on, a migration that can be missing without breaking the rest ("unavailable" answers, as worksheets do).

**Non-Goals:**
- Moving skill practice, misconceptions or fading to the server. They stay device-reported and are labelled as such.
- Proctoring final quizzes (tab locking, cameras). The server clock and single sitting are the only integrity measures.
- Notifications by email or push for new tasks (push exists for photo requests only; extending it is a follow-up).
- Teacher-to-student messaging beyond the existing comments, notes and "look again" requests.
- Changing the teacher's personal 3/day AI allowance.

## Decisions

### D1. Quiz mode on the sitting, windows in their own table
Add `mode text not null default 'practice' check (mode in ('practice','final'))`, `started_at timestamptz`, `window_id uuid` to `math_quiz_sittings`. New `math_quiz_windows (id, class_id, unit_id, opens_at, closes_at, released_at, created_by_email)` with a partial unique index on open windows per `(class_id, unit_id)`. New `math_quiz_extra_sittings (id, window_id, student_id, until, reason, granted_by_email, used_sitting_id)`.

A final sitting is created by a new `POST /api/math/quiz-sittings/start` that checks the window (or an unused grant) and that the student has no final sitting in it, records `started_at` on the server, and returns the deadline. The existing submit route then accepts attempts for a final sitting only until `min(started_at + minutes + grace, closes_at or grant.until)`; photo uploads for attempts of a final sitting check the same deadline.

*Alternatives*: a per-class "max attempts / best or latest" policy (rejected by the product decision: practice is unlimited, final is once); keeping the clock on the page (rejected: the final grade must not depend on the device).

Practice sittings keep today's flow (page clock, created at hand-in) so nothing changes for existing users.

### D2. Official grade and release computed on read
`sitting_view` gains `mode`, `window_id`, `released`. "Official grade" = grade of the latest handed-in final sitting per unit. For a student, a final sitting's grade, per-question points and solutions are withheld unless `released_at` is set on its window (or on the grant's window); the teacher always sees them. A sitting released with open checks shows its grade when the checks complete (no extra state needed: release is a window flag, grade is computed on read).

### D3. Skill tags on quiz questions
Add `skills: [skill_id, ...]` (1–3, same unit) to each `units[].quiz.questions[]` in `app/math_algebra9.json`; validate in `app/math_skills.py` at load. Lost points per skill are computed on read from checked answers of the last 60 days. This feeds the practise-before-retake list, the focus profile and exam readiness.

### D4. Focus profile computed in the browser, quiz evidence from the server
The class report already gets each student's progress and quiz sittings. Add per-question `skills` and earned/possible points to the sittings it returns, and compute the weakness score in a new `Sky.focus(progress, sittings, skills)` helper shared by the report and the student's exam view. Score per skill = `2·lost_quiz_points/25 + wrong_14d + 2·(started && !done) + 1·fading`, capped and ranked. The weights are a starting point kept in one constant table, tested, and may be tuned without spec changes.

*Alternative*: compute on the server. Rejected for now: misconceptions and fading are device data already computed client-side by `Sky.*`; duplicating that logic in Python would drift.

### D5. Focus practice as an audience on assignments
Add `student_emails text[]` (nullable; null = whole class) to `math_assignments`. *Revised during implementation:* the audience is kept by email, not account id, because the class lists its students by email and a student who has not signed in yet has no id. `worksheets_only()` becomes `allowed_items(user, fields, old)`: managers may give anything; class teachers may give worksheets to the class, or 1–5 skill items when `student_ids` is set. The student listing keeps an assignment when it has no audience or the student's email is in it, on the server; a student is told only that an assignment is personal, never whom else it was given to. Report completion counts only the audience. Path markers and `Sky.assignmentState` need no change beyond receiving the filtered list.

*Alternative*: a separate `math_focus_practice` table. Rejected: it would duplicate due dates, completion, report tabs and the student card.

### D6. Worksheet versions and return-for-fix
Today one row per `(worksheet_id, student_id)` is replaced in place. Change to versioned rows: add `version int not null default 1`, `state text check (state in ('submitted','checked','returned'))`, `note text (<=300)`, `returned_at`, `return_comment`, `return_due_on date`; replace the unique constraint with `unique (worksheet_id, student_id, version)`. Before a check, a new hand-in still replaces the current version (as today); after a return, it creates `version+1`. The current submission is the highest version. Existing rows migrate to `version 1`, `state = checked_at is null ? 'submitted' : 'checked'`.

The completion rule (done = has a submission; late = handed in after due) uses the current version; a returned current version counts as not done, and its due date becomes `return_due_on` when set.

### D7. Worksheet hand-in from the phone
*Revised during implementation.* This already exists: each page of a worksheet hand-in is a `worksheet:<id>` answer attempt (`POST /api/math/worksheet-attempts`), photographed on this device or on the phone through the normal answer-scan flow (request, confirm before the camera, review, upload), and the page then adds it to the hand-in. It meets the spec (same account, confirm and review steps, pages bound to their worksheet), so no new table is added; the work is to keep it working with the note and the versioned submissions of D6.

### D8. Task list and grades as read-model routes
`GET /api/math/my-tasks` and `GET /api/math/my-grades` assemble, for the signed-in student only, assignments (filtered by audience), open windows/grants, worksheet submissions, sittings and reviews. They do not take a student id. The state order in the task-hub spec is implemented once in `Sky.taskState` and used by the student's list and the teacher's views, so both always agree.

### D9. Batches and a class budget for AI checks
Add `batch_id` to `math_ai_requests` (the class is found from the student's email, as the queue already does); new `math_ai_batches (id, class_id, scope_kind, scope_id, created_by_email, total, sent, created_at)`; new `math_class_ai_budget (class_id, day date, used int, primary key (class_id, day))` plus `classes.ai_daily_checks int` (null → default 150) and `classes.auto_send_practice bool default false`.

The budget is taken with an atomic Postgres function `take_class_checks(class_id, day, n, limit) returns int` (how many were granted) and given back with `give_class_checks`. It is in the database, not in memory like `TeacherQuota`, because batches run across requests and restarts and the number matters for cost.

`POST /api/ai-queue/batches` takes a scope (window, unit practice, worksheet), collects the class's pending requests oldest first, takes up to `n` from the budget, marks them `sending` with the `batch_id`, and processes them in a background worker with a small concurrency (2–3) to respect provider rate limits. The existing per-request `send` route uses the class budget for `grading` requests and the teacher quota for `photo` requests. *Revised during implementation:* worksheet AI checks do not become queue requests (the queue's rows are tied to one answer attempt); a single or batch worksheet check takes from the same class budget and stores the suggestion on the submission (`ai_score`, `ai_comment`, `ai_readable`, `ai_checked_at`), where it only fills the teacher's review form.

Auto-send for practice: when a practice sitting is handed in and `auto_send_practice` is on, its requests go straight into a system batch, within the budget; whatever does not fit stays pending.

*Alternatives*: raise the teacher's personal limit (rejected: mixes the teacher's own use with class work, and still needs 100+ clicks); auto-send everything (rejected by the product decision: final and worksheet checks wait for the teacher).

### D10. Exam entries with units
Extend each `classes.exams` entry with optional `units: [unit_id]` and `note` (≤300). *Revised during implementation:* the exam board had no editor in the app, so a new route, `PUT /api/classes/{id}/exams/topics` (class teacher or manager), sets an existing exam's units (⊂ the class's units) and note; the report's "מבחנים" tab uses it. No migration needed (JSON column). Readiness and the plan are computed in the browser from progress, `Sky.focus` and the student's sittings; plan step completion is derived from progress state (skill done/reviewed after the plan was first opened, practice sitting after that time, practice exam over the exam's units after that time), so no new storage.

### Relation to in-flight changes
This change only adds requirements. Where it narrows earlier behaviour it does so through new states, not by contradicting text:
- `assignment-worksheets` "Replace after the check → refused" still holds for a checked submission; "returned" is a new state that allows a new version.
- `unit-quiz-grades` "report shows the server's sittings" still holds; the report now labels each sitting practice/final and shows the official grade from final sittings.
- `class-assignments` "Class teacher creates assignments" is narrowed in code by `worksheets_only()`; D5 widens it for per-student skill items only.

Recommended order: archive the seven listed changes (sync their specs into `openspec/specs/`) before archiving this one, so a later edit can use MODIFIED deltas against real main specs.

## Risks / Trade-offs

- [Device-reported data in the focus profile can be stale or edited] → every piece of evidence is labelled by source (spec), and quiz evidence, which drives the most weight, is server-checked.
- [Weakness weights feel arbitrary to teachers] → evidence is shown in words next to each skill; weights are one tested constant table.
- [AI cost spikes from batch sends] → per-class daily budget in the database, manager-set; teacher sees the count before confirming; failed checks are given back.
- [Provider rate limits on a 100-check batch] → background worker with small concurrency and retry with back-off; students see "checking" meanwhile.
- [Final-quiz windows across midnight / time zones] → all window times stored as `timestamptz`, shown in Jerusalem time, same as due dates.
- [Versioned worksheet rows break code that assumes one row per student] → a single helper `current_submission()` used everywhere; migration keeps existing rows as version 1; tests cover old rows.
- [Releasing with open checks surprises a student later] → confirmation names how many sittings are still open.
- [Several unarchived predecessor changes] → listed above; no requirement here contradicts them.

## Migration Plan

1. Supabase migrations, each independent and additive: quiz modes and windows; assignment audience; worksheet versions and scans; AI batches and class budget. Each feature answers "unavailable" when its migration is missing (existing pattern), so code can deploy first.
2. Content: add `skills` to the 4 unit quizzes' questions; validation fails loudly in CI if a tag is missing.
3. Deploy server, then front end. Existing sittings become practice; existing worksheet submissions become version 1; existing assignments keep `student_ids = null`.
4. Rollback: front end and routes can be reverted alone; new columns are nullable/defaulted and ignored by old code, except the worksheet unique constraint — the down migration restores `unique (worksheet_id, student_id)` after deleting non-current versions (data loss of earlier versions only, documented).

## Open Questions

- Default class budget (150) and auto-send default (off) may be tuned after the first weeks of use; they are settings, not spec changes.
- Whether the teacher's daily summary of the inbox should also go by push notification is left to a follow-up change.
