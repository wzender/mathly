-- Mathly 2: timed, graded attempts (lesson quizzes now; exercise tests and the simulation later). Additive (new objects only).
-- Read and written only by the server with the secret key: row-level security is on, there are no policies, and the browser roles
-- get no grants (as in m2_classes).
-- Rollback: drop table m2_attempts;
begin;

-- One timed try. `questions` is the ordered list of bank references [{skill_id, key}], `answers` maps the question key (which starts with its skill id) to the chosen
-- choice position. An attempt with submitted_at null is open; the server settles it (grades it, sets timed_out) on the first read
-- after due_at. `grade` is a whole number 0-100, stored when the attempt is settled.
create table public.m2_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  kind text not null check (kind in ('quiz', 'exercise_test', 'simulation')),
  scope text not null,
  started_at timestamptz not null default now(),
  due_at timestamptz not null,
  submitted_at timestamptz,
  timed_out boolean not null default false,
  grade integer check (grade between 0 and 100),
  questions jsonb not null default '[]'::jsonb,
  answers jsonb not null default '{}'::jsonb,
  check (due_at > started_at)
);
create index m2_attempts_user_kind_scope on public.m2_attempts (user_id, kind, scope);

alter table public.m2_attempts enable row level security;
revoke all on public.m2_attempts from public, anon, authenticated;
grant all on public.m2_attempts to service_role;
commit;
