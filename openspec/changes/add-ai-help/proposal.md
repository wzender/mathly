# Proposal

## Why

Students get stuck on problems outside the bank, and teachers cannot check every written answer alone. mathly1's AI help does both while students never call the AI themselves: every request goes through the teacher, within a budget (PRD 4.15, STU-6, TCH-5).

## What Changes

- Photo help: a student photographs a problem; after the teacher sends it, the AI's hints come one at a time, with the steps and answer only on request.
- AI checks of handwritten answers: a suggested score and comment for the teacher; the teacher's grade wins; students can ask to look again.
- The teacher's AI queue: send, decline with a note, or send a batch.
- Budgets: per class per day (default 150) and 3 personal requests per teacher per day.
- Privacy: the AI is off per class until a manager switches it on; no names or emails go to the AI.
- Clear messages when the AI fails, and a record of every call's cost.

Screens: `docs/mockups/mathly2-screens.html` (student tab: photo help on home; teacher tab: AI queue).

## Capabilities

### New Capabilities
- `ai-help`: the queue, photo help, AI checks, budgets, failures, cost records and privacy (PRD AI-1 – AI-10, STU-6, TCH-5).

### Modified Capabilities

## Impact

- Builds on `written-answers`, `assignments` and the class AI switch and budget from `accounts-and-classes`.
- New `m2_` tables for requests, reviews, budgets and usage. Uses `ANTHROPIC_API_KEY` and `MATH_MODEL`.
- Ports mathly1's `app/math_photo.py`, `app/answer_grading.py`, `app/ai_queue.py`, `app/ai_batches.py`, `app/teacher_ai.py`, `app/ai_usage.py` behavior.
