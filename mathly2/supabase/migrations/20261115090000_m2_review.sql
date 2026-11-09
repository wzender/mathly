-- Mathly 2: the review list (חזרה). Every wrong answer (path practice, a lesson quiz, a practice test, the simulation; an unanswered question of a
-- quiz or test too) is one row per student and question. A right answer in the review tab deletes the row and is logged in m2_review_done, which
-- the daily goal counts (m2_daily_correct is redefined to add it). Redoing a question here never touches m2_answers, so mastery and practice rounds are unchanged.
-- Additive, plus a redefined view with the same columns. No policies and no browser grants, as in the other m2_ tables.
-- Rollback: create or replace view public.m2_daily_correct as select user_id, day, count(*)::integer as correct from public.m2_answers where correct group by user_id, day;
--           drop table public.m2_review_done, public.m2_review;
begin;

create table public.m2_review (
  user_id uuid not null,
  question_key text not null,
  skill_id text not null,
  source text not null check (source in ('practice', 'quiz', 'exercise_test', 'simulation')),
  wrong_at timestamptz not null default now(),
  primary key (user_id, question_key)
);
create index m2_review_user_when on public.m2_review (user_id, wrong_at);

create table public.m2_review_done (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  day date not null,
  question_key text not null
);
create index m2_review_done_user_day on public.m2_review_done (user_id, day);

create or replace view public.m2_daily_correct as
  select user_id, day, count(*)::integer as correct
  from (select user_id, day from public.m2_answers where correct
        union all
        select user_id, day from public.m2_review_done) as t
  group by user_id, day;

alter table public.m2_review enable row level security;
alter table public.m2_review_done enable row level security;
revoke all on public.m2_review, public.m2_review_done from public, anon, authenticated;
grant all on public.m2_review, public.m2_review_done to service_role;
grant usage, select on sequence public.m2_review_done_id_seq to service_role;
commit;
