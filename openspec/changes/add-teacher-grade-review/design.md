# Design

## Context

- Open answers: `math_question_attempts` (question snapshot), `math_answer_attachments` (photo), `math_answer_grades` (AI checks, `result` jsonb with `verdict`, `score`, `feedback`, `transcription`, `solution`). They are read through the owner-checked `math_answer_action`/`math_grade_action` RPCs as the student (`app/answer_scans.py`).
- The teacher → students mapping already exists in `app/ai_queue.py` (`watched`: class teachers see the non-teacher emails of their classes, managers see everyone).
- The AI queue keeps handled rows for a day, so after that the teacher has no way back to an answer. The class report (after `add-server-quiz-grades`) knows each sitting's attempt ids.
- A correct open skill answer completes the skill on the student's device (`static/math.js`, `P.done[questionId]` set from `grading.finished_at` when the verdict is correct).

## Goals / Non-Goals

**Goals:**
- The teacher can read and review any checked answer of their students, at any time.
- The student sees the teacher's word clearly, and can ask for it.

**Non-Goals:**
- Free-form chat threads (one comment per review, and the dispute message, are enough for now).
- Reviewing multiple-choice answers.
- Push notifications for new comments (the home notice is enough. A later change can reuse `app/push.py`).

## Decisions

**Separate review table, AI check unchanged.** `math_teacher_reviews(id, attempt_id, user_id (student), reviewer_email, score int null check 0..100, comment text check len ≤ 1000, created_at, seen_at null)`, latest row per attempt wins. The AI's `math_answer_grades.result` is never edited, so the transparency requirement ("AI check" still visible) is free and history is kept. Alternative considered: writing the override into `result`. Rejected because it loses the AI's original and mixes trust levels.

**Requests table.** `math_review_requests(id, attempt_id, user_id, message ≤ 300, state open|closed, created_at, closed_at)` with a unique partial index on `(attempt_id) where state='open'`. Saving a review closes the open request for that attempt in the same transaction (service-only RPC).

**Teacher access path.** New routes in `app/teacher_review.py`:
- `GET /api/teacher/answers/{attempt_id}` → question snapshot, checks, latest review, open request.
- `GET /api/teacher/answers/{attempt_id}/image` → the photo bytes (`Cache-Control: no-store`).
- `PUT /api/teacher/answers/{attempt_id}/review` `{score?, comment?}`.
- `GET /api/teacher/review-requests` → open requests of the teacher's students.

Each route resolves the attempt's owner with the service key, maps it to an email, and checks it against `watched(user)`. The `watched` helper moves from `ai_queue.py` into `app/access.py` (or a shared `classes` helper) so both modules use one rule.

**Student side.** The existing attempt read adds `teacher_review: {score, comment, at}` (latest) and `review_request` state. New routes `POST /api/math/answer-attempts/{id}/review-request {message}` and `GET /api/math/teacher-comments` (unseen reviews). Opening an attempt sets `seen_at` on its latest review.

**Effective score.** One helper `effective_score(check, review)` returns `review.score` if set, else `check.score`. The sitting grade from `add-server-quiz-grades` and the attempt payload's `effective_score` both use it. The device's skill completion reads `effective_score == 100` from a teacher review as well as an AI `correct` verdict.

**Where the teacher opens answers.** The unit-quiz rows in the class report become buttons opening the sitting's answers. Handled AI-queue rows get an "open answer" link. The AI queue sheet gets a second tab "בקשות לבדיקה חוזרת" with a count on the header button.

## Risks / Trade-offs

- [The teacher's photo access widens who can read a student's image] → Same population that already sees the photo in the AI queue (class teacher, managers). Checked on every request, never by a public URL.
- [A student spams "look again" requests] → One open request per answer, and a limit of 5 open requests per student, like the AI queue.
- [A teacher score of 100 completing a skill could be unexpected] → It is shown to the teacher in the form ("100 מסמן את המיומנות כהושלמה").

## Migration Plan

1. Apply the additive migration after `add-server-quiz-grades`'s migration.
2. Deploy. Without the tables, teacher review routes return 503 `review_unavailable`, and the student pages show no teacher section.
3. Rollback: previous code. Tables can stay.
