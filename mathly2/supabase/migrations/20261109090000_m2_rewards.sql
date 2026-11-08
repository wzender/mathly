-- Mathly 2: rewards. Additive (new objects only). Read and written only by the server with the secret key:
-- row-level security is on, there are no policies, and the browser roles get no grants (as in m2_classes).
-- Rollback: drop view m2_last_answered; drop table m2_comets, m2_reward_state;
begin;

-- The newest answer day per student and skill (helped and wrong answers count): fading stars read it.
create view public.m2_last_answered as
  select user_id, skill_id, max(day) as day
  from public.m2_answers
  group by user_id, skill_id;

-- The comets a student caught.
create table public.m2_comets (
  user_id uuid not null,
  comet_id text not null,
  caught_at timestamptz not null default now(),
  primary key (user_id, comet_id)
);

-- The day a comet last crossed for the student, and the day one was last caught (one catch per crossing).
create table public.m2_reward_state (
  user_id uuid primary key,
  last_comet_day date,
  last_catch_day date
);

alter table public.m2_comets enable row level security;
alter table public.m2_reward_state enable row level security;
revoke all on public.m2_last_answered, public.m2_comets, public.m2_reward_state from public, anon, authenticated;
grant all on public.m2_last_answered, public.m2_comets, public.m2_reward_state to service_role;
commit;
