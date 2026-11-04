# Proposal

## Why

The class teacher's report shows each student's unit-quiz (בוחן מסכם) grade, but that grade is computed in the student's browser and saved in the progress object that the student's device uploads unchecked (`PUT /api/math/progress`). A student who edits that object in the browser's developer tools can show the teacher any grade. The real per-answer checks already live on the server (`math_answer_grades`), so the grade the teacher sees can come from there. This must be fixed before the teacher's view is extended (see `add-class-attention-view`, `add-teacher-grade-review`), because those features build on the same grades.

## What Changes

- Record each unit-quiz sitting on the server when the student submits it: the unit, its attempts in question order, when it was submitted and whether the time ran out.
- Compute a sitting's score on the server from the stored checks and the quiz's point weights in `app/math_algebra9.json`. A sitting has no score until every answered question has a completed check with a score, and a question without a photographed answer earns 0.
- Show the student the server's score on the quiz result screen. The browser no longer decides it.
- The class report reads unit-quiz grades only from the server's sittings, never from the uploaded progress object.
- Mark in the report that skill progress, gold stars and practice-exam results come from the student's device ("נתוני תרגול מהמכשיר"), so the teacher knows which numbers are checked and which are not.
- Sittings from before this change (only in the progress object) appear in the report as "not verified" without a grade.

## Capabilities

### New Capabilities

- `unit-quiz-grades`: recording unit-quiz sittings on the server and computing their grades from the stored checks, for the student and for the class report.

### Modified Capabilities

(none: there are no main specs yet)

## Impact

- New migration `supabase/migrations/<ts>_math_quiz_sittings.sql`: the service-only `math_quiz_sittings` table.
- `app/answer_routes.py`: a submit route for sittings and a read route for a student's own sittings.
- `app/class_report.py`: reads sittings for the class's students. It stops passing `uq[].history[].score` from the progress object.
- `static/math.js`: `uqSubmit` posts the sitting. `uqResult` shows the server's score. The report shows server grades and marks device-reported data.
- `static/guide.js` (teacher tab) and `README.md` (class teacher section, migration step).
- Tests: `tests/test_unit_quiz.py`, `tests/test_class_report.py`.
