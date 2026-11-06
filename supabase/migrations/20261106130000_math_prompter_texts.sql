-- The prompter's saved texts (app/prompter.py): a developer's scripts, kept with the account so they are on every device.
-- Additive: one new table; nothing existing changes. Only the server's secret key reads or writes it.
begin;
create table public.math_prompter_texts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 120),
  body text not null check (char_length(body) <= 100000),
  updated_at timestamptz not null default now()
);
create index math_prompter_texts_user on public.math_prompter_texts(user_id, updated_at desc);
alter table public.math_prompter_texts enable row level security;
revoke all on public.math_prompter_texts from public, anon, authenticated;
grant select, insert, update, delete on public.math_prompter_texts to service_role;
commit;
