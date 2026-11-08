# Tasks

## 1. Real tests (data and rules)

- [x] 1.1 Add the migration `20261111090000_m2_tests.sql` (decision 1) and the store methods to create, read, change, soft-remove and list a class's tests, in both stores; verify unit tests, request tests for the Supabase store, and migration tests on PostgreSQL (defaults 12 and 45, the limits on questions and minutes, the browser roles are refused)
- [x] 1.2 Add `countdown.py` (decision 2): the plan for a test set 9 or more days ahead and for short notice, and today's task from the closest test; verify unit tests for 12 days (finish the path), 9 (exercise test 1), 7 (exercise test 2), 5 (simulation), 3 after a simulation with two failed skills (review one of them), 1 (light mixed review), a test set 6 days ahead keeps the order within 6 days, a done step moves to the next one early, and with tests in 4 and 10 days the task comes from the one in 4
- [x] 1.3 Add `readiness.py` (decision 5); verify unit tests: 60 → 60, (80, 70, 90) → 81, (100, 95, none) → 80 with `capped`, each label at its edges, and "מוכנים" never shown without a simulation
- [x] 1.4 Add the exercise-test and simulation draw (decision 3); verify unit tests with a fixed `rng`: test 1 with 7 weak needed and 3 weak skills gives 3 weak and 9 other, test 2 takes 30%, a not-started skill is never drawn and is listed under "practise first", a skill answered wrong in an earlier exercise test counts as weak, a retake takes new questions while enough remain, the simulation spreads one per skill round after round, and nothing started gives no questions

## 2. The API

- [x] 2.1 Add the teacher's routes: `GET /api/teaching/tests`, `POST /api/classes/{id}/tests`, `PUT` and `DELETE /api/tests/{id}` (decision 6); verify API tests: defaults 12 and 45, lessons outside the class are refused, a past date is refused, a change after the date is refused, removing keeps the students' grades, moving the date moves every student's days left, 22 of 25 took the simulation shows 22 and names the 3, a teacher of another class gets 404, and the permission matrix test lists every new route
- [x] 2.2 Add `GET /api/home` and `GET /api/tests/{id}` for students; verify API tests: no test gives only the next skill, a test 9 days away with exercise test 1 not taken gives it as today's task, a test 4 days away with the simulation open and not taken marks it required, two tests take the task from the closer one, readiness has M, E and S as they exist, and a student of another class gets 404
- [x] 2.3 Add starting exercise tests and the simulation, and let the attempt routes read, answer and submit them (decisions 3 and 4); verify API tests: an exercise test has the test's questions and minutes, starts early (11 days before), resumes when open, a retake draws new questions and the best grade counts; the simulation is refused 8 days before with its opening date, has 12 questions and 45 minutes, can be taken once (a second start returns the result), and its failed skills become the review list; no served question carries a right answer or a skill name
- [x] 2.4 Add exercise tests and simulations to `GET /api/grades`; verify API tests that the grades list each test's best exercise grades and the simulation grade, and that a removed test keeps its name there

## 3. Student screens

- [x] 3.1 Move the tab bar to the bottom with בית, מסלול, ציונים and האוסף, the card to open home at `#/subject/math`, and the path to `#/subject/math/path` (decision 7); update the browser tests that open the path; verify a Playwright test that the card opens home, each tab opens its screen, the bar stays at the bottom at 360px with 44px targets and covers nothing, and a link to a skill still opens the path with its sheet
- [x] 3.2 Build `home.js`: the closest test with days left, the readiness bar with M, E, S and the cap note, one button for today's task, the required simulation, other tests, and "continue the path"; verify a Playwright test for no test, a test 9 days away (the button opens exercise test 1), a test 4 days away with the simulation required, the readiness bar's parts and cap note, and that nothing scrolls sideways at 360px
- [x] 3.3 Build the test's card at `#/test/<id>`: the plan with recommended days and done marks, both exercise tests with best grade and start or retake, "practise these first" with links, and the simulation (when it opens, required, its result and review list); verify a Playwright test of each state
- [x] 3.4 Generalise `quiz.js` to the three kinds (title, retake only for quiz and exercise test, once-only note for the simulation) and add the addresses `#/exam/...` and `#/sim/...`; verify a Playwright test that an exercise test runs with the test's length and timer and shows its weak skills as links at the end, that the simulation cannot be started twice, and that the quiz tests still pass
- [x] 3.5 Add exercise tests and simulations to the grades screen; verify a Playwright test that both appear with their grades

## 4. Teacher screen

- [x] 4.1 Add the tests tab to `teacher.js`: per class, set a test (date, lesson checkboxes, note, questions, minutes with defaults), edit or remove it, "N מתוך M עשו סימולציה" with the names of those missing, and each student's readiness; verify a Playwright test that a teacher sets a test with the defaults, changes its date, sees who has not taken the simulation, and removes it, at 360px and on a computer

## 5. Wrap-up

- [x] 5.1 Walk the whole countdown in a browser with the server's clock moved day by day: the teacher sets a test 12 days ahead; the student's home asks to finish the path, then offers exercise test 1, takes it, then exercise test 2, then the required simulation, then a review skill, and the readiness bar moves and loses its cap after the simulation; the teacher sees the simulation taken; verify the test passes
- [x] 5.2 Update `docs/mockups/mathly2-screens.html` where home, the bottom tab bar or the teacher's tests tab no longer match what was built; verify by opening it beside screenshots
- [x] 5.3 Run `venv/bin/python -m pytest mathly2/tests` and `openspec validate add-test-readiness --strict`; verify both pass

## Workflow follow-up

- Apply the new migration after the six earlier ones (on a test project first).
- Archive this change once it is reviewed (it creates six capabilities and modifies `learning-path`); then propose `add-written-work` (stage 6), which adds assignments, the teacher sending an exercise test as one (EXT-2), and assignment rows on home and the grades screen.
