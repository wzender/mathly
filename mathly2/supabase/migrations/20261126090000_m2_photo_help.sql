-- Mathly 2: help on a photographed question (photoq.py): the conversation with the AI, how much of the solution was revealed, and the
-- grade it can still reach (help lowers it: a direction 90, the first step 75, each further step 10 less, the full solution 40).
-- Safe to run again. Rollback: alter table public.m2_photo_questions drop column chat, drop column revealed, drop column max_grade;
begin;
alter table public.m2_photo_questions add column if not exists chat jsonb not null default '[]'::jsonb;
alter table public.m2_photo_questions add column if not exists revealed integer not null default 0 check (revealed between 0 and 20);
alter table public.m2_photo_questions add column if not exists max_grade integer not null default 100 check (max_grade between 0 and 100);
commit;
