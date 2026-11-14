-- Mathly 2: the AI review of the way (הדרך) in a practice test or the simulation, sent back to the student after handing in (boardreview.py).
-- {"state": "pending" | "done" | "failed", "summary", "questions": {question key: {verdict, feedback, tip}}, "at"}. Additive.
-- Rollback: alter table public.m2_attempts drop column review;
alter table public.m2_attempts add column review jsonb;
