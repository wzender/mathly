# Proposal

## Why

The teacher can watch the class but cannot ask it to do anything in the app. Homework still happens outside Mathly, so the path's skills, the unit quizzes and the practice exams are disconnected from what the teacher planned for the week. Students decide alone what to practise, and the teacher has no way to check that "practise Pythagoras before Thursday" happened. Assignments make the teacher's plan part of the student's path and give the teacher a reason to open the report.

## What Changes

- The class teacher (or a manager) can create an **assignment (משימה)** for a class: a title, an optional note, a due date, and one or more items:
  - **skills** to finish (from the class's units),
  - a **unit quiz** to submit,
  - a **practice exam** to take over chosen units.
- The teacher can edit or delete an assignment. Students see changes the next time they load.
- Students see **"משימות מהמורה"** on their home screen above the path: each open assignment with its due date, the items, how many are done, and a button that opens the next unfinished item. Overdue assignments are marked. Finished ones move to a "done" list for 14 days.
- Skills on the path that belong to an open assignment get a small marker.
- An item is done when:
  - a skill: the skill is finished (at any time, including before the assignment),
  - a unit quiz: a sitting for the unit was submitted after the assignment was created (server record from `add-server-quiz-grades`),
  - a practice exam: a practice exam covering all the chosen units was taken after the assignment was created.
- The class report gets an **"משימות"** tab: each assignment with how many students finished it, and per student which items are done, late or missing. Students with an overdue unfinished assignment are added to the "needs attention" list (from `add-class-attention-view`).

## Capabilities

### New Capabilities

- `class-assignments`: assignments a class teacher gives a class (items, due date), how students see and complete them, and how the teacher follows them.

### Modified Capabilities

(none: there are no main specs yet. The attention signal for overdue assignments is specified here, as a requirement on this capability.)

## Impact

- New migration `<ts>_math_assignments.sql`: table `math_assignments`, service-only.
- New module `app/assignments.py`: CRUD routes for the class teacher and managers, and a read route for students (assignments of their classes).
- `static/math.js`: the teacher's create/edit form, the "משימות" report tab, the student's home card and path markers, completion computed from progress and server sittings.
- `static/math.css`, `static/guide.js` both tabs, `README.md`.
- Tests: new `tests/test_assignments.py`, browser tests.
- Depends on `add-server-quiz-grades` (unit-quiz items) and `add-class-attention-view` (attention signal). Without the latter the signal is simply not shown.
