-- Mathly 2: a mistakes round (חזרה על הטעויות) after a quiz, an exercise test or the simulation: the questions it got wrong, answered again
-- with instant feedback as practice. Kept as m2_attempts rows of kind mistakes_round (scope: the handed-in attempt's id). One widened check.
-- Rollback: delete from public.m2_attempts where kind = 'mistakes_round';
--           alter table public.m2_attempts drop constraint m2_attempts_kind_check;
--           alter table public.m2_attempts add constraint m2_attempts_kind_check check (kind in ('quiz', 'exercise_test', 'simulation', 'lesson_round'));
begin;
alter table public.m2_attempts drop constraint m2_attempts_kind_check;
alter table public.m2_attempts add constraint m2_attempts_kind_check check (kind in ('quiz', 'exercise_test', 'simulation', 'lesson_round', 'mistakes_round'));
commit;
