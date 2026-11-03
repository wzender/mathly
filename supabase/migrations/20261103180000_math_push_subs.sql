-- Push subscriptions of phones (app/push.py): a phone is notified when the computer asks for a photo of an answer.
-- Additive: one new table; nothing existing changes. Only the server's secret key reads or writes it.
begin;
create table public.math_push_subs (
  endpoint text primary key check (endpoint like 'https://%' and length(endpoint) <= 1000),
  user_id uuid not null references auth.users(id) on delete cascade,
  p256dh text not null check (length(p256dh) between 1 and 200),
  auth text not null check (length(auth) between 1 and 100),
  created_at timestamptz not null default now()
);
create index math_push_subs_user on public.math_push_subs(user_id);
alter table public.math_push_subs enable row level security;
revoke all on public.math_push_subs from public, anon, authenticated;
grant select, insert, update, delete on public.math_push_subs to service_role;
commit;
