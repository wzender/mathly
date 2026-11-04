# Tasks

## 1. Sitting storage

- [x] 1.1 Add migration `supabase/migrations/<ts>_math_quiz_sittings.sql`: table `math_quiz_sittings` (id, user_id → auth.users on delete cascade, unit_id, attempt_ids uuid[], submitted_at, time_up, client_key, unique(user_id, client_key)), RLS on, service_role only. Verify it applies cleanly to the disposable test PostgreSQL used by `tests/scan_support.py`.
- [x] 1.2 Add the grade function (points × check score, 0 for a missing photo, open while any photographed answer lacks a scored completed check). Verify with unit tests covering all-checked, waiting, unreadable, needs_review and missing-photo cases.

## 2. Student routes

- [x] 2.1 Add `POST /api/math/quiz-sittings` with ownership, question-position checks and an idempotent `client_key`. Verify with tests in `tests/test_unit_quiz.py`: success, another student's attempt, wrong question order, repeated submit returning the same id.
- [x] 2.2 Add `GET /api/math/quiz-sittings?unit_id=` returning the grade, open count and per-question points. Verify with a test where one check completes after submission and the grade appears.
- [x] 2.3 In `static/math.js`, make `uqSubmit` post the sitting (with retry on next open when it failed) and make `uqResult` show the server grade. Verify with a browser test where the device progress has a forged score and the screen shows the server's.

## 3. Class report

- [x] 3.1 In `app/class_report.py`, load sittings and their grades for the class's students and stop sending `uq` scores from the progress object. Verify in `tests/test_class_report.py` that a forged progress score does not appear and the server grade does.
- [x] 3.2 In the report UI, show server grades, "ממתין לבדיקה" for open sittings, "לא מאומת" for old device-only sittings, and the device-data label on the skills and practice-exam sections. Verify with a browser test of the report.
- [x] 3.3 Update the teacher tab in `static/guide.js` and the class-teacher and migration sections of `README.md`. Verify `tests/test_guide_browser.py` still passes.

## 4. Integration

- [ ] 4.1 Run the full `pytest` suite and check by hand, on a local Supabase project, that a submitted quiz checked through the AI queue shows the same grade to the student and the teacher.
