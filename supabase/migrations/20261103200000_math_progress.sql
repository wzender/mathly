-- Each student's path progress (app/progress.py), so it follows the account to every device.
-- Additive: one new table; nothing existing changes. Only the server's secret key reads or writes it.
begin;
create table public.math_progress (
  user_id uuid primary key references auth.users(id) on delete cascade,
  data jsonb not null check (jsonb_typeof(data) = 'object'),
  updated_at timestamptz not null default now()
);
alter table public.math_progress enable row level security;
revoke all on public.math_progress from public, anon, authenticated;
grant select, insert, update, delete on public.math_progress to service_role;
commit;
