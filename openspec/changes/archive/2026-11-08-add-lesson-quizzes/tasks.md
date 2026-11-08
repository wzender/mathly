# Tasks

## 1. The attempt engine

- [x] 1.1 Add the migration `20261110090000_m2_attempts.sql` for `m2_attempts` (decision 1) and the store methods to create, read, save answers of and settle an attempt, list a student's attempts, and read open attempts, in both stores; verify unit tests for each, that one student's attempts are never read for another, request tests for the Supabase store, and migration tests on PostgreSQL (the table's defaults, the browser roles are refused)
- [x] 1.2 Add `attempts.py` with `grade` and `settle` (decisions 2 and 5) and the result builder; verify unit tests: 7 of 10 gives 70, 8 of 12 gives 67, an unanswered question counts as wrong, a settled attempt is graded from the answers saved, settling twice changes nothing, an attempt before `due_at` is not settled, and the result lists the lost skills and the mistake name and tip but never a `correct` flag, a right choice or its position (checked over the whole JSON)
- [x] 1.3 Add `quiz.py` with `draw` (decision 4); verify unit tests with a fixed `rng`: a lesson of 4 skills gives 10 questions with every skill at least 2, 6 skills give quotas 2,2,2,2,1,1, 2 skills give 5 and 5, a skill without questions is left out and the others still give 10, a retake takes only unused questions while enough remain (two attempts in a row never repeat) and then the least-used, and the draw is the same for the same `rng`

## 2. The API

- [x] 2.1 Add `GET /api/lessons/{id}/quiz` and `POST /api/lessons/{id}/quiz/start` (decisions 3 and 6); verify API tests: a new student starts a quiz with 10 questions and `due_at` 15 minutes after the server's now, starting again resumes the same open attempt, a lesson the student's classes do not have gives 404, a manager is refused, and no served question carries `correct`, `mistake` or a skill name
- [x] 2.2 Add `GET /api/attempts/{id}`, `PUT /api/attempts/{id}/answers` and `POST /api/attempts/{id}/submit`; verify API tests: an answer is saved and can be changed, submitting grades it, submitting twice returns the same result, an answer after `due_at` is refused with 409 and settles the attempt, a read 20 minutes after a 15-minute start returns the submitted attempt with the answers given and `timed_out`, a device clock change changes nothing, another student gets 404, and an unknown question or choice gives 422
- [x] 2.3 Add `GET /api/grades` and the `quiz` facts on each lesson in `GET /api/path`; verify API tests: 60 then 85 gives 85, 85 then 70 stays 85, a lesson never attempted has no grade, an overdue open attempt is settled by the grades read, and the permission matrix test lists every new route and passes
- [x] 2.4 Check the written quizzes are not used: a lesson whose unit has an authored `quiz` in the bank still gets the 10-question multiple-choice quiz; verify the API test with that lesson, and that the draw never reads the unit's `quiz`

## 3. The screens

- [x] 3.1 Add the quiz node to the trail after each lesson's ring, its three states in words, and the tab bar with "ציונים"; verify a Playwright test that every lesson shows a node with "○ עוד לא נעשה", a best grade shows "✓ הציון: 85", an open attempt shows "◐ בוחן פתוח", the node is a link reachable with Tab, and nothing scrolls sideways at 360px
- [x] 3.2 Build `quiz.js`: the sheet at `#/quiz/<id>` with the countdown from the server's `due_at`, "שאלה n מתוך 10" with dots, shuffled choices saved on tap, previous and next, the board and calculator per question, and the submit with its warning about unanswered questions; verify a Playwright test that the quiz opens with 10 questions and no skill names, a choice is saved and survives a reload on the same attempt and the same timer, no right or wrong is shown, the board opens with its calculator, and the submit shows the warning
- [x] 3.3 Add the result: the grade, the lesson's best, the lost skills as links to their stars, the missed questions with the mistake's name and tip, and "בוחן חוזר"; verify a Playwright test that a quiz with two misses in one skill lists that skill with its link and two mistakes, no right answer appears anywhere in the page, a timed-out attempt shows the result after the server settles it, and a retake draws new questions
- [x] 3.4 Add the grades screen at `#/grades`; verify a Playwright test that it says "עוד אין ציונים" when empty, shows each lesson's best grade, attempts and date after quizzes, shows the better of two attempts, and fits 360px

## 4. Wrap-up

- [x] 4.1 Walk a quiz end to end in a browser: sign in as a student, open a lesson's quiz from the trail, answer all 10, submit, see the grade and the lost skills, open one, close back to the path where the node shows the grade, and find it on the grades screen; verify the test passes
- [x] 4.2 Update `docs/mockups/mathly2-screens.html` only where the quiz node or the grades tab no longer match what was built; verify by opening it beside a screenshot of each
- [x] 4.3 Run `venv/bin/python -m pytest mathly2/tests` and `openspec validate add-lesson-quizzes --strict`; verify both pass

## Workflow follow-up

- Apply the new migration after the five earlier ones (on a test project first).
- Archive this change once it is reviewed, so `lesson-quizzes` and `grades` move into `openspec/specs/`; then propose `add-test-readiness` in full (design and tasks), which reuses `attempts.py` for exercise tests and the simulation.
