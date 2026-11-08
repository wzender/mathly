-- Mathly 2: practice is a round of a skill's questions, each shown once. The server must remember where the current round began.
-- `round_start` is how many answers the student had on the skill when the round began; the round is the answers after that.
-- It is null for a student who practised before this change: their earlier answers all count as past rounds.
-- Additive (one new column on an m2_ table). Rollback: alter table public.m2_skill_progress drop column round_start;
begin;
alter table public.m2_skill_progress add column round_start integer check (round_start is null or round_start >= 0);
commit;
