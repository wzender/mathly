## Context

mathly1 has the AI pieces (photo solver, answer grader, queue, batches, usage). mathly2 has written work (pictures, submissions, an inbox for the teacher), a class AI switch and budget, and a private picture store. Students must never call the AI: the teacher is always in the loop (PRD 4.15).

## Decisions

- **One table of requests** `m2_ai_requests`: `kind` is `photo` (a student's photographed problem), `check` (an AI check of a handed-in answer) or `again` (a student asks the teacher to look again; no AI call). State: `waiting` → `processing` → `done` / `failed`, or `declined` / `cancelled`. The result, the teacher's note and a failure record (reason and technical detail) are columns. A check keeps a stored copy of the question (`snapshot`), so a later change to the bank or the assignment does not change an old check.
- **The AI runs in a small background pool.** Sending marks the request `processing` and returns; the student's page and the teacher's queue look again every few seconds while open. A batch is the same send, many times, so it never holds the page. A server restart leaves `processing` rows: on start they are returned to `waiting`.
- **Budgets are rows taken in one step.** `m2_ai_allowance(scope, day, used)` with a SQL function `m2_ai_take(scope, day, n, cap)` that adds only when the cap allows and says whether it did, and `m2_ai_give_back`. Scopes: `class:<id>` (the class's daily checks) and `teacher:<email>` (3 a day). The in-memory store takes under a lock. The Israel date is the day.
- **Help photos are a new picture kind** (`help`) in the private bucket, read only through the server by the student, the class's teacher and a developer. The photo is deleted when the AI call has finished, or the request is declined or cancelled, so it is not kept (a failed call keeps it for the retry until the teacher declines).
- **The AI is behind an interface** (`solve(image, media_type, skills)` and `grade(images, snapshot)`), real with `ANTHROPIC_API_KEY`, a fake in tests. Without a key a send fails with the reason "missing key" and tells who can fix it.
- **What a check sends:** the stored question (the assignment's title, note and, for a bank quiz, its questions with points) and the answer pictures; for a pages assignment also the teacher's page pictures first. No name or email.
- **Where a student asks:** a photo help sheet (exercise screen header and a home card, only when the class has the AI on); an "ask for an AI check" button on a handed-in, not yet graded answer; an "ask to look again" button on a checked or graded answer.

## Risks

- A model's output cannot be trusted: the check is a suggestion and fails closed (an unreadable or unsure answer gets no score), the teacher's grade always wins.
- Cost: bounded by the class budget and the teacher's allowance, and every call's tokens and estimated cost are recorded.
- Privacy: the AI is off for a class until a manager turns it on; nothing that names a student is sent.
