# Tasks

- [x] 1.1 Add `writtentest.py`: the plain-number box, comparing a typed answer, a question's points from the teacher or the AI, the grade once known, the result. Verify with `test_writtentest_api.py`.
- [x] 1.2 Hand in the simulation without a grade (`attempts.py`), serve it without choices and save typed answers (`quizzes.py`). Verify with the API tests.
- [x] 1.3 Check written boards with the AI and set the grade after the check (`boardreview.py`); the teacher's check is final (`boardwork.py`). Verify with the fake AI and the teacher tests.
- [x] 1.4 Leave a simulation waiting for its check out of readiness, grades and the mistakes round (`realtests.py`, `quizzes.py`, `rounds.py`). Verify with the API tests.
- [x] 1.5 The student's screen: the board and the box, "בבדיקה", the result with points; the teacher's screen: the right and typed answers. Verify with the browser tests (an AI check, and no AI).
- [x] 1.6 Update the PRD (SIM, GRD). Verify that `openspec validate written-simulation --strict` passes.
