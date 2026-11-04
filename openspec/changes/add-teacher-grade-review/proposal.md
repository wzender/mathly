# Proposal

## Why

The teacher's only power over a checked answer is to approve or decline it before the AI sees it. After the AI grades it, the teacher cannot fix a wrong grade, cannot grade an answer the AI marked unreadable or "needs review", and cannot say anything personal to the student. The guide even tells students that "the automatic check can be wrong, show your teacher", but the app gives the teacher no way to act on that. Personal feedback on real work is also the strongest link between the teacher and the student, and today there is none.

## What Changes

- The class teacher (or a manager) can open any checked open answer of their students: the photo, the question, the AI's transcription, verdict, score and feedback. They reach it from the class report (unit-quiz rows and the student's card) and from handled requests in the AI queue.
- The teacher can **set a teacher score** (0–100) on that answer, replacing the AI's score, and **write a comment** to the student. Both are optional, and saving either creates a teacher review.
- The teacher can give a score to answers the AI left without one (unreadable, needs review), so such a quiz can get a grade.
- The student sees the teacher's comment and score on the answer, marked as coming from the teacher, above the AI feedback. The AI's original score stays visible as "AI check" for transparency.
- Unit-quiz grades (from `add-server-quiz-grades`) use the teacher score when there is one.
- An open skill answer that the teacher marks fully correct (100) completes the skill like a correct AI check does.
- The student can press **"לבקש מהמורה לבדוק שוב"** on a checked answer, with an optional short message. The request appears to the teacher in a "requests to look again" list (in the AI queue sheet) and on the student's report card. It closes when the teacher saves a review.
- The student's home screen shows a small notice when a teacher has commented on one of their answers since they last looked.

## Capabilities

### New Capabilities

- `teacher-answer-review`: the class teacher reviewing a student's checked open answer (teacher score, comment), the student asking for a review, and how the student sees it.

### Modified Capabilities

(none: there are no main specs yet. The `unit-quiz-grades` capability added by `add-server-quiz-grades` is extended in this change's spec by a requirement that the teacher score takes precedence.)

## Impact

- New migration `<ts>_math_teacher_reviews.sql`: tables `math_teacher_reviews` and `math_review_requests`, service-only.
- New module `app/teacher_review.py` with routes for teachers (read an answer with its image, save a review, list requests to look again) and for students (ask for a review, list unseen comments). It reuses the teacher→students mapping from `app/ai_queue.py` (`watched`).
- `app/answer_routes.py` / `app/answer_scans.py`: the attempt read for students includes the teacher review.
- Grade function from `add-server-quiz-grades`: teacher score first.
- `static/math.js`, `static/answer-scans.js`: the teacher's answer view and edit form, the student's display, the "look again" button and the home notice.
- `static/guide.js` both tabs, `README.md`.
- Tests: new `tests/test_teacher_review.py`, browser tests.
- Depends on `add-server-quiz-grades`.
