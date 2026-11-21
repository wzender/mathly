-- Mathly 2: two more kinds of m2_attempts rows. Safe to run again.
-- 'mistakes_round': answering again the questions a handed-in quiz, exercise test or simulation got wrong (rounds.py). The code made
--   these rows since that feature, but the kind check did not allow them, so the database refused them.
-- 'onthego_round': practice on the go (תרגול בנסיעה, onthego.py): questions that need no board, answered one by one on a phone.
-- Rollback: delete from public.m2_attempts where kind in ('mistakes_round', 'onthego_round');
--           alter table public.m2_attempts drop constraint m2_attempts_kind_check;
--           alter table public.m2_attempts add constraint m2_attempts_kind_check check (kind in ('quiz', 'exercise_test', 'simulation', 'lesson_round'));
begin;
alter table public.m2_attempts drop constraint if exists m2_attempts_kind_check;
alter table public.m2_attempts add constraint m2_attempts_kind_check
  check (kind in ('quiz', 'exercise_test', 'simulation', 'lesson_round', 'mistakes_round', 'onthego_round'));
commit;
