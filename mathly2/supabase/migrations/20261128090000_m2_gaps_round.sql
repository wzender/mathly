-- Mathly 2: one more kind of m2_attempts row. Safe to run again.
-- 'gaps_round': closing the gaps (השלמת פערים, rounds.py): GAP_PER_LESSON questions on each lesson behind the curriculum, answered one by
--   one; a lesson answered above GAP_PASS percent has its skills marked mastered and is no longer behind.
-- Rollback: delete from public.m2_attempts where kind = 'gaps_round';
--           alter table public.m2_attempts drop constraint m2_attempts_kind_check;
--           alter table public.m2_attempts add constraint m2_attempts_kind_check
--             check (kind in ('quiz', 'exercise_test', 'simulation', 'lesson_round', 'mistakes_round', 'onthego_round'));
begin;
alter table public.m2_attempts drop constraint if exists m2_attempts_kind_check;
alter table public.m2_attempts add constraint m2_attempts_kind_check
  check (kind in ('quiz', 'exercise_test', 'simulation', 'lesson_round', 'mistakes_round', 'onthego_round', 'gaps_round'));
commit;
