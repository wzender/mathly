-- Mathly 2: the work on the board (הדרך). Every answer keeps a picture of the student's board for that question (kind 'work' in m2_pictures),
-- one per student, attempt (or 'practice') and question in m2_work. A teacher can give a graded attempt's question partial or full credit for the
-- work: m2_attempts.credit maps a question key to 0, 0.5 or 1, and the grade is recomputed. Additive, plus one widened check.
-- No policies and no browser grants, as in the other m2_ tables.
-- Rollback: drop table public.m2_work; alter table public.m2_attempts drop column credit, drop column checked_at, drop column checked_by;
--           delete from public.m2_pictures where kind = 'work';
--           alter table public.m2_pictures drop constraint m2_pictures_kind_check;
--           alter table public.m2_pictures add constraint m2_pictures_kind_check check (kind in ('page', 'answer', 'help'));
begin;
alter table public.m2_pictures drop constraint m2_pictures_kind_check;
alter table public.m2_pictures add constraint m2_pictures_kind_check check (kind in ('page', 'answer', 'help', 'work'));

alter table public.m2_attempts add column credit jsonb not null default '{}'::jsonb;
alter table public.m2_attempts add column checked_at timestamptz;
alter table public.m2_attempts add column checked_by text;

-- `ref`: the attempt's id (a quiz, an exercise test, the simulation, a lesson round), or 'practice' for the exercise screen. The latest board wins.
create table public.m2_work (
  user_id uuid not null,
  ref text not null,
  question_key text not null,
  skill_id text not null,
  picture_id uuid not null references public.m2_pictures(id) on delete cascade,
  saved_at timestamptz not null default now(),
  primary key (user_id, ref, question_key)
);
create index m2_work_picture on public.m2_work (picture_id);

alter table public.m2_work enable row level security;
revoke all on public.m2_work from public, anon, authenticated;
grant all on public.m2_work to service_role;
commit;
