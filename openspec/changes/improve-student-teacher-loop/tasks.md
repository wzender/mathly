# Tasks

## 1. Quiz question skill tags

- [x] 1.1 Add `skills` (1–3 skills of the same unit) to every question of the 4 unit quizzes in `app/math_algebra9.json`; verify each tag by reading the question against the skill's description
- [x] 1.2 Validate quiz-question skills in `app/math_skills.py` (missing tag, foreign-unit tag, more than 3 fail with the unit and question named); verify with new cases in `tests/test_math_skills.py`
- [x] 1.3 Return per-question `skills`, earned and possible points from `sitting_view` in `app/quiz_grades.py`; verify in `tests/test_quiz_grades.py`

## 2. Practice and final unit quizzes

- [x] 2.1 Migration: `math_quiz_sittings.mode/started_at/window_id`, `math_quiz_windows`, `math_quiz_extra_sittings` (RLS on, service role only); verify it applies on a fresh database and old sittings read as `practice`
- [x] 2.2 Teacher routes to open, close and list final-quiz windows and to grant an extra sitting (class teacher or manager only); verify forbidden/overlap/foreign-unit cases in a new `tests/test_quiz_modes.py`
- [x] 2.3 `POST /api/math/quiz-sittings/start` for final sittings (window or unused grant, one per window, server `started_at`, returns deadline); verify before-window, second-start and grant cases in `tests/test_quiz_modes.py`
- [x] 2.4 Enforce the final deadline on photo upload and hand-in (quiz minutes + grace, capped by window/grant end); verify a late photo is rejected and the sitting is handed in with stored answers
- [x] 2.5 Block starting a practice sitting of a unit while the student has an open, not handed-in final; verify in `tests/test_quiz_modes.py`
- [x] 2.6 Official grade (latest final sitting) and release flag in `sitting_view`; withhold grade, points and solutions of an unreleased final from the student only; add the release route; verify both views in `tests/test_quiz_grades.py`
- [x] 2.7 Front end: quiz intro shows practice vs final, final confirmation dialog, server-driven clock on reload, "waiting for results" state; verify with a Playwright flow in `tests/test_unit_quiz.py`
- [x] 2.8 Practice result screen lists skills of questions that lost points with practise buttons and "ניסיון נוסף"; verify in the same Playwright file (lost points vs full marks)
- [x] 2.9 Class report labels sittings practice/final and shows the official grade; low-grade attention signal uses the official grade when present; verify in `tests/test_class_report.py`
- [x] 2.10 Update the user guide (`static/guide.js`) for students and teachers on practice vs final quizzes; verify the guide test still passes (`tests/test_guide_browser.py`)

## 3. Focus practice assignments

- [x] 3.1 Migration: `math_assignments.student_ids uuid[]` (null = whole class); verify existing rows read as class-wide
- [x] 3.2 Replace `worksheets_only()` with `allowed_items()` (teacher: worksheets for the class, or 1–5 skill items with an audience; manager: anything) and validate the audience is in the class; verify in `tests/test_assignments.py`
- [x] 3.3 Filter student assignment listings by audience on the server, and count report completion over the audience only; verify a non-chosen classmate gets nothing and the "1 מתוך 2" count
- [x] 3.4 Front end: focus-practice form (choose students, skills, due date), personal marker on the student's card, audience editing; verify with a Playwright flow
- [x] 3.5 Document focus practice in the teacher guide; verify the guide renders the new section

## 4. Worksheet versions, notes and return-for-fix

- [x] 4.1 Migration: versioned `math_worksheet_submissions` (`version`, `state`, `note`, `returned_at`, `return_comment`, `return_due_on`, unique per version) with existing rows as version 1; verify on a copy of current data
- [x] 4.2 One `current_submission()` helper used by completion, report and student views; verify all existing `tests/test_worksheets.py` cases still pass
- [x] 4.3 Hand-in accepts a note (≤300) and creates a new version after a return; refuses after a plain check; verify in `tests/test_worksheets.py`
- [x] 4.4 Return-for-fix route (comment 1–1000, optional new due date) and completion/late rules using the return due date; verify in `tests/test_worksheets.py`
- [x] 4.5 Front end: note field, receipt, returned state with comment, earlier versions list for student and teacher; verify in `tests/test_worksheets_browser.py`

## 5. Worksheet hand-in from the phone

- [x] 5.1 Keep the existing phone hand-in (each page a `worksheet:` answer attempt through the answer-scan flow, `POST /api/math/worksheet-attempts`) working with the note and versions of group 4; verify a phone page lands only under its worksheet in `tests/test_worksheets.py`
- [x] 5.2 The computer shows the phone's pages under the worksheet, ready to send with the note; verify with the existing phone Playwright flow in `tests/test_worksheets_browser.py` / `tests/test_phone_browser.py`

## 6. Student task hub

- [x] 6.1 `GET /api/math/my-tasks` (signed-in student only: audience-filtered assignments, open windows and grants, returned worksheets); verify in a new `tests/test_my_tasks.py`
- [x] 6.2 `Sky.taskState` with the spec's state order, used by the student list and teacher views; verify each state with unit cases in `tests/test_sky_browser.py`
- [x] 6.3 Front end: "המשימות שלי" list and the home-screen summary (count, nearest due); verify with a Playwright flow covering a mixed list and the empty state

## 7. Student gradebook

- [x] 7.1 `GET /api/math/my-grades` (server grades by unit: official final, practice best/latest, worksheet scores, waiting items, unseen teacher comments; ignores any student id); verify in a new `tests/test_my_grades.py`
- [x] 7.2 Front end: "הציונים שלי" page with kind labels, waiting states, new-comments block, links to results; verify with a Playwright flow
- [x] 7.3 Document the grades page in the student guide; verify the guide renders it

## 8. Exam preparation

- [x] 8.1 Accept optional `units` and `note` on exam entries in the class editor route, validating units against the class; verify in `tests/test_class_report.py` or the class editor tests
- [x] 8.2 `Sky.focus` helper (weakness score per skill from progress and sittings, constants in one table); verify with unit cases in `tests/test_sky_browser.py`
- [x] 8.3 Exam view: days left, units, note, per-skill readiness, misconceptions in the exam's units, latest grades; verify with a Playwright flow
- [x] 8.4 Preparation plan (ordered steps, daily amount, step completion derived from progress after the plan was opened, practice exam preset to the exam's units); verify the 6-steps/3-days and exam-tomorrow cases
- [x] 8.5 Teacher: class readiness per exam in the report; verify in `tests/test_class_report.py`
- [x] 8.6 Document exam preparation in the student and teacher guides; verify the guide renders it

## 9. Student focus profile

- [x] 9.1 Report data: include per-question skills and points of each student's sittings from the last 60 days; verify in `tests/test_class_report.py`
- [x] 9.2 "על מה לעבוד" section on the student card (top 5 skills with evidence in words, recurring misconceptions, source labels); verify with a Playwright flow
- [x] 9.3 Class-wide focus view (top 5 skills, top 3 misconceptions, student lists) with "לתת תרגול" opening the focus-practice form pre-filled; verify the pre-filled form in a Playwright flow

## 10. AI check batches and class budget

- [x] 10.1 Migration: `math_ai_requests.batch_id`, `math_ai_batches`, `math_class_ai_budget`, `classes.ai_daily_checks`, `classes.auto_send_practice`, AI-suggestion columns on worksheet submissions, and atomic `math_take_class_checks`/`math_give_class_checks` functions; verify concurrent takes never exceed the limit
- [x] 10.2 Class-budget accounting for student-work checks (grading, homework); teacher quota only for the teacher's own requests; give back on failure/unreadable; verify in `tests/test_ai_queue.py` and `tests/test_teacher_ai.py`
- [x] 10.3 `POST /api/ai-queue/batches` (scope: window, unit practice, worksheet; oldest first; partial when the budget is short) with a background worker of small concurrency and retry; verify partial batch and foreign-class exclusion in `tests/test_ai_queue.py`
- [x] 10.4 Worksheet AI checks (one or a batch) use the class budget and store the suggestion on the submission, where it only fills the review form; verify the student sees no score before the teacher saves
- [x] 10.5 Auto-send of practice-quiz checks per class (off by default); final and worksheet checks still wait; verify in `tests/test_ai_queue.py`
- [x] 10.6 Front end: batch button with count and budget left, per-class usage today/7 days, student-side check states; manager setting for the class budget; verify in `tests/test_ai_queue_browser.py`
- [x] 10.7 Update the AI-queue section of the teacher guide; verify the guide renders it

## 11. Teacher submissions inbox

- [x] 11.1 `GET /api/teacher/inbox?class_id=` (unchecked worksheet versions, quiz answers needing the teacher, open look-again requests; class teacher's classes, all for managers; filters); verify in a new `tests/test_inbox.py`
- [x] 11.2 Front end: inbox list with filters and open count, review in sequence (save → next), return-for-fix, and the report's "בחנים סופיים" tab (open/close a window, grant another sitting, release results with the open-checks confirmation); verify with a Playwright flow

## 12. Integration checks

- [x] 12.1 End-to-end Playwright scenario: teacher opens a final quiz → students sit it → teacher sends one batch → reviews an unreadable answer in the inbox → releases → student sees the grade on the grades page and the focus skills on the retake screen
- [x] 12.2 End-to-end Playwright scenario: teacher gives a worksheet → student hands in from the phone with a note → teacher returns it → student resubmits → teacher checks → both sides show the same states
- [ ] 12.3 Run the full test suite (`pytest`) and `openspec validate improve-student-teacher-loop --strict`; both pass

## Workflow follow-up

- Archive the predecessor changes (`add-class-assignments`, `add-assignment-worksheets`, `add-server-quiz-grades`, `add-teacher-grade-review`, `add-class-attention-view`, `add-misconception-patterns`, `add-open-question-phone-scan`) before archiving this one.
- Archive this change after review, and check the new main specs under `openspec/specs/`.
