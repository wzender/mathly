-- Mathly 2: a skill no longer has teaching stages (worked and faded examples were dropped from the plan), so the progress table
-- loses the two columns that remembered them. Only an m2_ table changes. The data that matters (the question on screen, help, when
-- the skill was started and mastered) is untouched.
-- Rollback: alter table public.m2_skill_progress add column stage text not null default 'example' check (stage in ('example', 'faded', 'practice')),
--   add column faded_done integer not null default 0 check (faded_done between 0 and 2);
begin;
alter table public.m2_skill_progress drop column stage;
alter table public.m2_skill_progress drop column faded_done;
commit;
