# Tasks

## 1. Storage and routes

- [ ] 1.1 Add migration `<ts>_math_assignments.sql` (`math_assignments`, cascade on class delete, service-only). Verify it applies on the test database and deleting a class removes its assignments.
- [ ] 1.2 Add `app/assignments.py` with teacher CRUD routes, item validation against the skills data and the class's units, and the class-teacher-or-manager rule. Verify in `tests/test_assignments.py`: create, foreign unit rejected, empty items rejected, other teacher 403, student 403, edit, delete.
- [ ] 1.3 Add `GET /api/math/assignments` for students (their classes' assignments in range, plus their unit-quiz sitting times). Verify a student in two classes gets both classes' assignments and none from other classes.

## 2. Completion

- [ ] 2.1 Add `assignmentState` in `static/math.js` implementing the completion rules (skill any time, unit quiz after creation, exam covering all units after creation, late after the Jerusalem end of the due date). Verify with a browser unit test on fixed fixtures for each scenario in the spec.

## 3. Student UI

- [ ] 3.1 Add the "משימות מהמורה" home card (open, late, done list for 14 days, continue button to the next item). Verify with a browser test for open, late and next-item navigation.
- [ ] 3.2 Mark assigned skills on the path with an accessible label. Verify in the browser test.

## 4. Teacher UI

- [ ] 4.1 Add the create/edit form (title, note, due date, item pickers limited to class units) and delete with a confirmation that names how many students started. Verify with a browser test that creates and edits an assignment.
- [ ] 4.2 Add the report's "משימות" tab with per-assignment counts and per-student item states. Verify with a browser test on a 3-student fixture.
- [ ] 4.3 Add the overdue-assignment signal to the "needs attention" list (if `add-class-attention-view` is in place). Verify in the report browser test.
- [ ] 4.4 Update `static/guide.js` (student: "משימות מהמורה"; teacher: creating and following assignments) and `README.md` (feature and migration). Verify `tests/test_guide_browser.py` passes.

## 5. Integration

- [ ] 5.1 Run the full `pytest` suite and check locally end to end: the teacher assigns two skills and a unit quiz, a student completes them, and the report shows the student as done.
