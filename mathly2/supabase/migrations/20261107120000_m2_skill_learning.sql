-- Mathly 2: skill learning. Additive (new objects only). Read and written only by the server with the secret key:
-- row-level security is on, there are no policies, and the browser roles get no grants (as in m2_classes).
-- Rollback: drop view m2_daily_correct; drop table m2_skill_progress, m2_answers;
begin;

-- One row per practice answer. Append-only: it is the evidence for mastery and for later weak-skill picks.
-- `day` is the Israel calendar day decided by the server when it stored the answer; `counted` is false when the
-- student opened help for that question (such an answer is skipped by the mastery rule).
create table public.m2_answers (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  skill_id text not null check (char_length(skill_id) between 1 and 80),
  question_key text not null check (char_length(question_key) between 1 and 120),
  correct boolean not null,
  counted boolean not null default true,
  mistake_id text,
  day date not null,
  answered_at timestamptz not null default now()
);
create index m2_answers_user_skill on public.m2_answers (user_id, skill_id, id);

-- What the server must remember between requests about one student and one skill.
-- `mastered_at` is set once, when the mastery rule is first met, and never cleared.
create table public.m2_skill_progress (
  user_id uuid not null,
  skill_id text not null check (char_length(skill_id) between 1 and 80),
  stage text not null default 'example' check (stage in ('example', 'faded', 'practice')),
  faded_done integer not null default 0 check (faded_done between 0 and 2),
  current_key text,
  current_helped boolean not null default false,
  started_at timestamptz,
  mastered_at timestamptz,
  primary key (user_id, skill_id)
);
create index m2_skill_progress_user on public.m2_skill_progress (user_id);

-- Correct practice answers per student and day: the daily goal and the streak. Helped answers count (effort).
create view public.m2_daily_correct as
  select user_id, day, count(*)::integer as correct
  from public.m2_answers
  where correct
  group by user_id, day;

alter table public.m2_answers enable row level security;
alter table public.m2_skill_progress enable row level security;
revoke all on public.m2_answers, public.m2_skill_progress, public.m2_daily_correct from public, anon, authenticated;
grant all on public.m2_answers, public.m2_skill_progress, public.m2_daily_correct to service_role;
grant usage, select on sequence public.m2_answers_id_seq to service_role;
commit;
