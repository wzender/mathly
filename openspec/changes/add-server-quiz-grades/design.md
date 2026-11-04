# Design

## Context

- A unit-quiz sitting exists only in the progress object `P.uq[unit]` in `static/math.js`: `{sitting, history:[{at, attempts, score, timeUp}]}`. `uqResult` fetches each attempt's check and computes `entry.score`, then `save()` uploads the whole object through `PUT /api/math/progress`. The server stores that object unchecked (`app/progress.py`).
- Each quiz question already has a server attempt, `math_question_attempts`, with `question_id = "quiz:<unit>:<index>"` (`app/answer_routes.py` `quiz_attempt`). Its photo is in `math_answer_attachments`, and its checks are in `math_answer_grades` (`result.score`, `result.verdict`).
- Point weights are in `app/math_algebra9.json` (`units[].quiz.questions[].points`).
- `app/class_report.py` `report_part` copies `uq` history, including the score, from the progress object into the report.

## Goals / Non-Goals

**Goals:**
- Unit-quiz grades in the report and on the result screen come only from server data.
- No change for the student beyond where the number comes from.

**Non-Goals:**
- Making multiple-choice skill progress, gold stars or practice exams server-verified. Their answers are checked in the browser, and moving that checking to the server is a much larger change. This change labels them instead.
- Teacher overrides of a grade (`add-teacher-grade-review` builds on this table).

## Decisions

**A sitting table rather than deriving sittings from attempts.** The server cannot tell which attempts form one sitting, because a retaken quiz creates new attempts for the same questions. A `math_quiz_sittings` row (`id, user_id, unit_id, attempt_ids uuid[], submitted_at, time_up, client_key`) states it explicitly. The unique `(user_id, client_key)` makes a repeated submit idempotent; the device generates `client_key` when the sitting starts. Alternative considered: storing a sitting id on each attempt. Rejected because it changes the attempt table that the scan flow relies on.

**Compute the grade on read, don't store it.** A grade is a pure function of the sitting's attempts, their latest completed checks and the points in the JSON. Computing it on read keeps it correct when a check finishes later (for example after the teacher sends it from the AI queue) without a trigger or a background job. Class sizes (about 30 students × 14 units) keep this cheap: one query for sittings and one for the latest checks of their attempts.

**Shared Python function for the grade.** `quiz_grade(unit, attempts, attachments, checks)` lives in a small module used by both the student's sitting route and the class report, so the two can never disagree.

**Routes.**
- `POST /api/math/quiz-sittings` `{unit_id, attempts:[...], time_up, client_key}` → `{id}`. Validates ownership, and that each attempt's `question_id` is `quiz:<unit>:<i>` with `i` matching its position.
- `GET /api/math/quiz-sittings?unit_id=` → the student's sittings with `grade`, `open` (questions still unchecked) and per-question points.
- The class report adds `quiz_sittings` per student, and `report_part` drops `uq[].history[].score`.

**Device copy stays.** `P.uq` keeps the sitting so a reload continues the clock, and `history[].score` stays in the device's progress for older frontends. The report ignores it.

## Risks / Trade-offs

- [Students who submitted before deploy lose their grade in the report] → They appear as "not verified". They can see their own past result as before, and the teacher can ask them to resubmit.
- [Submit request fails offline] → The device keeps the sitting marked `submitted` with `serverId` missing and retries the post on the next open of the quiz or the result screen.
- [Grade "drops" for a student who edited their progress] → Intended.

## Migration Plan

1. Apply the additive migration (new table, service-only, RLS on). No existing table changes.
2. Deploy the code. Without the table, the submit route returns 503 `quiz_sittings_unavailable` and the report shows quiz grades as unavailable instead of falling back to device data.
3. Rollback: deploy the previous code. The table can stay.
