# Tasks

## 1. The AI core

- [x] 1.1 Add the migration (`m2_ai_requests`, `m2_ai_allowance` with the take and give-back functions, `m2_ai_usage`, the `help` picture kind) and the store methods for them (in memory and Supabase); verify unit tests and the migration on a real PostgreSQL: the defaults and checks, browser roles refused, a take that would pass the cap is refused, two takes at once never pass it, a give-back restores it
- [x] 1.2 Add `ai.py`: the prompts, schemas, failure reasons, usage and cost ported from mathly1, the solver and grader behind an interface, a fake for tests, the settings (`ANTHROPIC_API_KEY`, `MATH_MODEL`), and the dependency; verify unit tests: every failure reason is told apart, the check fails closed on bad output (no score for unreadable or unsure, never 100 when inconsistent), the cost of a call, and that no payload holds a name or an email

## 2. Requests, the queue and the budgets

- [x] 2.1 Add the student's routes (make a photo request, ask for a check, ask to look again, list mine, read one, cancel) with the limits, the class choice and the AI-off refusal; verify API tests for each scenario of "Students never call the AI", "Cancel and decline" (student side), "AI privacy" and "Asking the teacher to look again"
- [x] 2.2 Add the teacher's routes (the queue with its number, send, decline, batch, own photo help) and the background run that records the result, the failure, the usage and the budget (taken before, given back on failure); verify API tests for "Who sends straight", "The teacher's AI queue", "Batches", "Budgets", "When the AI fails", "Usage and cost" and "AI check of a handwritten answer", including the permissions matrix and a restart returning processing requests to waiting

## 3. Screens

- [x] 3.1 Add the student's photo help sheet (camera or gallery, the reminder, the state, the hints one by one), its two entries (exercise screen header and the home card with the open requests), and the buttons on a handed-in or graded answer (ask for a check, ask to look again); verify Playwright tests: no button when the AI is off, the sheet shows waiting, then hints one at a time after the teacher sends, a declined note, cancel
- [x] 3.2 Add the teacher's AI tab with its number, the queue, send, decline with a note, batch, the failure details, the AI suggestion in the inbox review and the look-again requests in the inbox; verify Playwright tests: a request is sent and shows done, a failure shows its cause to the teacher, a batch with a short budget says so, the suggestion is shown beside the grade box and the teacher's grade is what is saved

## 4. Wrap-up

- [x] 4.1 Update the PRD where this changes it (the queue is a tab, `help` pictures, restart behavior); run the full suite and `openspec validate add-ai-help --strict`; verify both pass
