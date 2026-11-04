# Tasks

## 1. Storage and access rule

- [x] 1.1 Add migration `<ts>_math_teacher_reviews.sql`: `math_teacher_reviews`, `math_review_requests` (unique open request per attempt), and a service-only RPC that saves a review and closes the open request in one transaction. Verify it applies to the disposable test PostgreSQL and that a second open request on one attempt fails.
- [x] 1.2 Move the teacher→students rule (`watched`) out of `app/ai_queue.py` into a shared helper used by both modules. Verify `tests/test_ai_queue.py` still passes unchanged.

## 2. Teacher routes

- [x] 2.1 Add `app/teacher_review.py` with `GET /api/teacher/answers/{id}` and `/image`, checking the class-teacher rule. Verify in `tests/test_teacher_review.py`: class teacher allowed, other teacher 403, manager allowed, no image bytes on 403.
- [x] 2.2 Add `PUT /api/teacher/answers/{id}/review` with validation (score 0–100, comment ≤ 1000, not both empty). Verify the tests for correcting a score, grading an unreadable answer, the empty review and out-of-range values.
- [x] 2.3 Add `GET /api/teacher/review-requests`. Verify a request appears for its class teacher only and disappears after a review is saved.

## 3. Grades use the teacher score

- [x] 3.1 Add `effective_score` and use it in the unit-quiz grade function from `add-server-quiz-grades` and in the attempt payload. Verify with a test where a 25-point question's AI 40 / teacher 80 contributes 20 points.
- [x] 3.2 In `static/math.js`, complete an open skill when the teacher score is 100. Verify with a browser test.

## 4. Student side

- [x] 4.1 Include `teacher_review` and `review_request` in the student's attempt read, and set `seen_at` when opened. Verify with tests.
- [x] 4.2 Add `POST /api/math/answer-attempts/{id}/review-request` (one open per answer, at most 5 open per student) and `GET /api/math/teacher-comments`. Verify tests for the duplicate and limit cases.
- [x] 4.3 Show "הערת המורה" with the teacher score above the AI feedback on quiz results and open skill answers, the "לבקש מהמורה לבדוק שוב" button with its message field, and the home notice. Verify with browser tests in `tests/test_answer_browser.py`.

## 5. Teacher UI

- [x] 5.1 Add the teacher's answer view (photo, question, AI check, review form, "100 completes the skill" hint), opened from the report's unit-quiz rows and from handled AI-queue rows. Verify with a browser test that saves a review and sees it in the report.
- [x] 5.2 Add the "בקשות לבדיקה חוזרת" tab in the AI queue sheet with a count on the header button. Verify with a browser test.
- [x] 5.3 Update both tabs of `static/guide.js` (the student "בדיקה דרך המורה" section and the teacher "תור AI"/"דוח הכיתה" sections) and `README.md`. Verify `tests/test_guide_browser.py` passes.

## 6. Integration

- [x] 6.1 Run the full `pytest` suite and check end to end locally: student submits a quiz, the teacher sends it to the AI, the student disputes one answer, the teacher corrects it, and the student sees the new grade and comment.
