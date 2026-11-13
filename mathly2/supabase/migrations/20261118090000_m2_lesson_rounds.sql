-- Mathly 2: lesson rounds (סבב שיעור), a short round of a lesson's skills with instant feedback, kept as m2_attempts rows of kind
-- lesson_round (scope: the lesson id). Its answers are also stored as practice answers in m2_answers. One widened check.
-- Rollback: delete from public.m2_attempts where kind = 'lesson_round';
--           alter table public.m2_attempts drop constraint m2_attempts_kind_check;
--           alter table public.m2_attempts add constraint m2_attempts_kind_check check (kind in ('quiz', 'exercise_test', 'simulation'));
begin;
alter table public.m2_attempts drop constraint m2_attempts_kind_check;
alter table public.m2_attempts add constraint m2_attempts_kind_check check (kind in ('quiz', 'exercise_test', 'simulation', 'lesson_round'));
commit;
