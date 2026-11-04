-- Assignments a class teacher gives a class (app/assignments.py): skills to finish, a unit quiz, a practice exam, by a
-- date. Additive: one new table, read and written only with the server's secret key.
begin;
create table public.math_assignments (
  id uuid primary key default gen_random_uuid(),
  class_id bigint not null references public.classes(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 80),
  note text not null default '' check (char_length(note) <= 500),
  due_on date not null,
  items jsonb not null check (jsonb_typeof(items) = 'array' and jsonb_array_length(items) between 1 and 20),
  created_by_email text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index math_assignments_class on public.math_assignments(class_id, due_on desc);
alter table public.math_assignments enable row level security;
revoke all on public.math_assignments from public, anon, authenticated;
grant all on public.math_assignments to service_role;
commit;
