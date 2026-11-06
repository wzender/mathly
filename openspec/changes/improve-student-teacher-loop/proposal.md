# Proposal

## Why

Mathly now has the pieces of a classroom loop — assignments with worksheets, server-graded unit quizzes, teacher reviews of AI checks, an AI queue, a class report — but they are scattered, and the loop between student and teacher breaks in a few places:

- A student has no single place that says "what do I owe, what is coming, how did I do". Assignments sit on the home screen, the exam board only lists a subject and a date, unit-quiz grades are hidden inside each quiz's intro, and worksheet scores only appear on the assignment card until it drops off after 14 days.
- Every unit quiz can be retaken without limit, and the report quietly shows the latest sitting. There is no way to give a quiz "for real" once, and no way to say "retake it, but practise first". The clock of a sitting is kept only by the student's page.
- The exam board does not say what an exam covers, so the app cannot help a student prepare for it.
- The teacher sees a student's signals (stuck skills, recurring misconceptions, low quiz grades) in different tabs, and cannot act on them: class teachers can only give worksheets, and only to the whole class.
- AI checking of student work does not scale: each queued student answer uses one of the teacher's 3 daily AI requests, so a 4-question quiz for a class of 27 (108 answers) cannot realistically be checked. A worksheet submission, once checked, can never be sent back for a fix.

This change closes those gaps so that the same loop — teacher gives work → student prepares and hands in → AI checks → teacher confirms → student sees the result and what to do next → teacher sees who needs what — works end to end.

## What Changes

**Student side**
- A "My tasks" hub (`המשימות שלי`): one list of open assignments, open final quizzes, and work returned for a fix, ordered by due date, with a clear state per item (not started / in progress / handed in / waiting for check / checked / returned / late).
- Worksheet hand-in improvements: hand in from the phone (reusing the same-account phone flow), an optional note to the teacher, a visible receipt, and a resubmit path when the teacher returns the work for a fix.
- Two kinds of unit quiz: **practice** quizzes (retake any time, own grade history, never the official grade) and **final** quizzes (opened by the class teacher for a time window, one sitting per student, server-kept clock, the official grade). The teacher can give one student another final sitting (for example after an absence or a technical failure).
- Retaking a practice quiz shows what to practise first: the skills behind the questions the student lost points on.
- A grades page (`הציונים שלי`): all server grades — final quizzes, practice quizzes (best and latest), worksheet scores — with teacher comments, items still waiting for a check, and a link to each result.
- Exam preparation: the exam board entries can name the units they cover; the student gets a per-exam readiness view (skills finished / fading / not started, recurring misconceptions in those units, last practice-quiz grade) and a preparation plan with one-tap practice (due skills, a practice exam preset to the exam's units, the unit's practice quiz).

**Teacher side**
- A per-student focus profile in the class report: the student's weakest skills, recurring misconceptions, questions lost in final/practice quizzes mapped to skills, overdue work, and a short trend — each with the evidence behind it.
- Class-level weakness summary: the skills and misconceptions shared by most students.
- Focus practice: a class teacher may assign skill items to chosen students (one or more), straight from the focus profile. Class-wide skill / quiz / practice-exam items stay manager-only.
- Submissions inbox: one list of everything waiting for the teacher — worksheet submissions, final-quiz answers, "look again" requests — with filters by assignment and state, and a "return for a fix" action on worksheets.
- AI check batches: the teacher approves a whole batch (a final quiz's answers, a worksheet's submissions) in one action. Checks of student work draw from a per-class daily AI budget, separate from the teacher's personal 3 requests. AI results are shown as suggestions the teacher confirms or corrects; nothing reaches the student as a grade before the rule for that item says so.

**Content data**
- Unit-quiz questions get skill tags (which skills each question tests), so lost points can be mapped to skills.

Nothing here is **BREAKING** for existing data: existing unit-quiz sittings become practice sittings, and existing assignments, worksheets and reviews keep working.

## Capabilities

### New Capabilities
- `student-task-hub`: the student's single list of owed work and its states, worksheet hand-in from the phone, the note to the teacher, the hand-in receipt and resubmission after a return.
- `unit-quiz-modes`: practice vs. final unit quizzes, final-quiz windows opened by the teacher, one official sitting, server-kept clock, extra sittings granted by the teacher, practise-before-retake guidance.
- `student-gradebook`: the student's grades page and what each grade shown there means.
- `exam-preparation`: exams linked to units, the per-exam readiness view and the preparation plan.
- `student-focus-profile`: the teacher's per-student and class-wide weakness views and the evidence behind each signal, including quiz-question skill tags.
- `focus-practice-assignments`: class teachers assigning skill practice to chosen students.
- `teacher-submissions-inbox`: one queue of work waiting for the teacher, returning worksheets for a fix.
- `ai-check-batches`: batch approval of AI checks for student work, the per-class AI budget, and AI results as suggestions the teacher confirms.

### Modified Capabilities
None under `openspec/specs/` (the main specs directory is empty). This change builds on capabilities still held in unarchived changes — `class-assignments`, `assignment-worksheets`, `unit-quiz-grades`, `teacher-answer-review`, `class-report`, `misconception-patterns` — and adds to them through the new capabilities above without contradicting their requirements (see design.md, "Relation to in-flight changes").

## Impact

- **Server**: `app/assignments.py` (per-student targeting, teacher-allowed skill items), `app/worksheets.py` (note, return-for-fix state, phone hand-in), `app/quiz_grades.py` and the quiz-sitting routes (mode, windows, server clock, official grade), `app/ai_queue.py` and `app/teacher_ai.py` (batches, class budget), `app/class_report.py` (focus profile data), `app/main.py` (exam entries with units). New routes for the student task list, grades, final-quiz windows, inbox and batches.
- **Database (Supabase migrations)**: `math_quiz_sittings` gets `mode` and server `started_at`; new `math_quiz_windows` and `math_quiz_extra_sittings`; `math_assignments` gets an optional `student_ids` audience; `math_worksheet_submissions` gets `note`, `state`, `returned_at`, `return_comment`, `version`; `math_ai_requests` gets `batch_id`, `class_id`; new `math_ai_batches` and `math_class_ai_budget`; `classes.exams` entries may carry `units`.
- **Front end**: `static/math.js` (task hub, grades page, exam preparation, quiz modes, focus profile, inbox, batch approval), `static/answer-scans.js` (worksheet hand-in from the phone).
- **Content**: `app/math_algebra9.json` unit-quiz questions gain `skills` tags; validation in `app/math_skills.py`.
- **Cost**: AI spend for student work becomes predictable per class (budget) rather than bounded by each teacher's 3/day.
- **Tests**: unit tests per route, and Playwright end-to-end flows for the student task hub, final quiz, return-and-resubmit and batch approval.
