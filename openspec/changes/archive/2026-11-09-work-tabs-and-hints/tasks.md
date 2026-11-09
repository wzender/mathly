# Tasks

## 1. A button that takes time shows it

- [x] 1.1 Add one hook that every request goes through: the button or form submitter that started it gets a spinner after about a third of a second, ignores a second press until the request ends, and shows "…" under reduced motion; covers `api()` and the picture uploads, so every button in the app (teacher, manager, admin, developer, student) is covered without editing each handler; verify a Playwright test with a held request for a button of each kind (a plain button, a form's submit, a picture upload), a quick request shows nothing, a second press during the wait sends nothing, and the state clears after success and after an error

## 2. The teacher's counts

- [x] 2.1 Add `GET /api/teaching/counts` (classes taught, tests, assignments, submissions waiting) and show the number on every tab of the teacher's screen, refreshed after each action; verify API tests (2 classes, 3 tests, 4 assignments, 5 waiting; a removed test or assignment is not counted; another teacher's items are not counted; the permission matrix) and a Playwright test that the numbers show on all four tabs and change after grading

## 3. The student's home and the new tab

- [x] 3.1 Make home show only what is critical: remove the other-tests list and the notifications card from home, list the other tests on the test's card, and show under "המשימות שלי" only the new assignments; verify a Playwright test with several tests and assignments in every state (home shows the nearest test, a required simulation, only the new assignments, and the continue button)
- [x] 3.2 Add the "הגשות" screen and tab (the tab bar becomes בית, מסלול, הגשות, ציונים, האוסף, still readable at 360px) with every assignment grouped by state, the sent-back note, the grade and note of checked ones, "באיחור", and the notifications switch at the bottom; verify a Playwright test of each group, that every assignment is listed, and that the switch moved from home

## 4. Wrap-up

- [x] 4.1 Run `venv/bin/python -m pytest mathly2/tests` and `openspec validate work-tabs-and-hints --strict` and `openspec validate add-written-work --strict`; verify all pass

## Note

- Archive `add-written-work` first: its assignments requirements ("My assignments", "Submissions tab") were changed there, because its delta is not archived yet.
