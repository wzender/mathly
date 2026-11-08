# Tasks

## 1. Bank and rules

- [x] 1.1 Change the bank check to the single static solved example (`worked_example` = question, steps of `do` and text `why`, answer) and stop checking faded examples (decision 1); verify tests pass for a valid example and fail for a step without `why` or an example without an answer, and the real bank still loads
- [x] 1.2 Change `scripts/draft_examples.py` to draft one solved example per skill in that shape (no faded examples); verify its tests with the fake client for draft, a flagged draft and merge, and that the dry run sends nothing and leaves the bank unchanged
- [x] 1.3 Add `recent_skills(user_id, n)` and `solved_keys(user_id, skill_id)` to both stores; verify unit tests for each, including that other students' answers do not count, and request tests for the Supabase store
- [x] 1.4 Add `learning.next_skill` (decision 2); verify tests for the four scenarios in `learning-path`: continuing, a new student gets the first skill, a just-mastered last answer moves the marker, and everything mastered gives none

## 2. API

- [x] 2.1 Reshape `GET /api/skills/{id}` and remove `POST /api/skills/{id}/stage` (decision 2); verify tests that a skill with and without a solved example both open at their question, `solved` and `total` are right, `requires` and `opens` list the neighbours, a skill with no questions has no question, and the permission matrix test is updated and passes
- [x] 2.2 Keep answering, help and stale-question refusal on the reshaped skill; verify the `skill-mastery` and `exercise-screen` scenarios through the API: two days, one day, wrong answer, help between correct answers, mastery not undone months later, a device clock change, no correct flag anywhere in a served question, the next question differs, and a stale key is refused
- [x] 2.3 Reshape `GET /api/path`: the lessons of the student's classes (every lesson for a teacher or developer), each skill with its state, `next`, today's goal and streak; verify tests for a student of two classes, a student whose class has one lesson, the marker rule, and that a manager is refused

## 3. The smart board

- [x] 3.1 Copy `math-board.js`, `board-math.js` and `vendor/mathlive/` unchanged, and add `board.css` (the board's block, the sheet, layer and scrim rules, and the variable map from the sky tokens); verify the files are byte-identical to mathly1's and a Playwright test loads the board in light and dark with no console error
- [x] 3.2 Test the board's behaviour in a browser: it opens full screen on a phone and beside the sheet on a 1280px desktop, every tool has its Hebrew label, a pen stroke changes the canvas and undo restores it, the question can be copied onto it and the eraser leaves the copy, a sketch stays when moving between two questions, and nothing is sent to the server; verify the test passes
- [x] 3.3 Test the calculator in a browser: it opens from the toolbar, sin 30 in degrees shows 0.5, and 7 × 6 shows 42; verify the test passes

## 4. The path screen

- [x] 4.1 Add the star, ring arcs and spark drawings to `sky.js` and the path styles to `app.css` (decision 3); verify a Playwright test draws rings for lessons of 2, 3 and 6 skills at 360px, with every star inside the screen and none over the hub
- [x] 4.2 Rewrite `path.js` as the trail of hubs with start and end markers, numbered stars, state symbol and word, and the owl on the next star; verify a Playwright test that a student sees only their class's lessons, each state shows its word, a mastered star differs from a learning one, the owl is on the next star, and nothing scrolls sideways at 360px in light and dark
- [x] 4.3 Test the path's access: every star is a link reachable with Tab and opened with Enter, its accessible name has the number, the name and the state, and no animation runs with reduced motion; verify the test passes

## 5. The exercise screen

- [x] 5.1 Build `exercise.js`: the sheet over the path with the header, explanation, "question n of N" with dots, the question with its figure, shuffled choices and tap-to-answer (decision 4); verify a Playwright test that opening a skill shows its parts, the same question can be shown in a different order, and the server grades by the bank position
- [x] 5.2 Add the right and wrong answers: the celebration, the count in a row and the skippable countdown; the quiet wrong answer with the mistake's name and tip, a link to the skill to go back to when the bank names one, and a different next question; verify a Playwright test for each, that no choice is marked as correct, and that mastering a skill is announced
- [x] 5.3 Add the "?" help (explanation, solved example if any, and "this answer will not count") and the requires and opens chips; verify a Playwright test that help makes the next right answer not count toward mastery, a chip opens its skill, and a skill without a solved example shows only the explanation
- [x] 5.4 Add resuming and stale answers: reopening shows the question that was on screen, and a refused answer reloads the current question; verify a Playwright test with two tabs, and a skill with no questions says there is no practice yet
- [x] 5.5 Close the sheet back to a refreshed path and honour `#/skill/<id>` links and reloads; wire the header's board button and mount the board for every question (decision 5); verify a Playwright test that closing shows the updated star, a link opens the sheet over the path, and the board opens from the sheet's button with a sketch per question

## 6. Cleanup and integration

- [x] 6.1 Delete the worked and faded screens, `skill.js`, the stage logic and their tests (decision 6); verify no file refers to `faded` or `/stage`, the tests still pass, and the old "stage" mockup note in `docs` is not left behind
- [x] 6.2 Walk one skill end to end in a browser: sign in as a student, open it from the path, answer two right on Monday, move the server clock to Tuesday, answer one more, see it mastered on the path with the owl moved on; verify the test passes
- [x] 6.3 Run `venv/bin/python -m pytest mathly2/tests` and `openspec validate add-learning-core --strict`; verify both pass

## 7. Subject choice, sign-in logo and dark sky (align with mathly1)

- [x] 7.1 Copy mathly1's `logo.svg` and show it on the sign-in page; verify a Playwright test that the sign-in page shows the logo and no content
- [x] 7.2 Make the app always dark with a starry sky (foundation decision 6); verify a Playwright test that a light-mode device still gets the dark background and that the tests for light mode are removed
- [x] 7.3 Add the subject cards (PTH-9) as the student's first screen, with the path at `#/subject/math`, a way back, and direct links to a skill still working; verify a Playwright test for the card, its progress bar, opening the path, going back and a deep link

## Workflow follow-up

- Archive this change once it is reviewed, so `skill-mastery`, `exercise-screen`, `learning-path` and `smart-board` move into `openspec/specs/`; then propose `add-rewards` in full (design and tasks).
- Check pen pressure, palm rejection and the full-screen board on a real tablet and phone (a headless browser cannot).
