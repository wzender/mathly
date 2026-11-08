-- Mathly 2: real tests a teacher sets for a class. Additive (new objects only). Read and written only by the server with the secret key:
-- row-level security is on, there are no policies, and the browser roles get no grants (as in m2_classes).
-- The two exercise tests and the simulation of a test are not rows: they exist because the test exists, and their tries are
-- m2_attempts rows (kind exercise_test / simulation, scope "<test id>:1", "<test id>:2" or "<test id>").
-- Rollback: drop table m2_tests;
begin;

create table public.m2_tests (
  id bigint generated always as identity primary key,
  class_id bigint not null references public.m2_classes(id) on delete cascade,
  date date not null,                                   -- the test day (Israel calendar)
  lessons text[] not null default '{}',
  note text not null default '',
  questions integer not null default 12 check (questions between 1 and 40),
  minutes integer not null default 45 check (minutes between 5 and 180),
  created_by text not null,
  created_at timestamptz not null default now(),
  removed_at timestamptz,                               -- soft delete: grades already earned keep their test's name
  check (cardinality(lessons) > 0)
);
create index m2_tests_class on public.m2_tests (class_id) where removed_at is null;

alter table public.m2_tests enable row level security;
revoke all on public.m2_tests from public, anon, authenticated;
grant all on public.m2_tests to service_role;
grant usage, select on sequence public.m2_tests_id_seq to service_role;
commit;
