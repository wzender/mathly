-- Claude API usage (app/ai_usage.py): one row per call, with its tokens and estimated cost, for the Monitoring tab.
-- Additive: one new table; nothing existing changes. Only the server's secret key reads or writes it.
begin;
create table public.math_ai_usage (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  user_id uuid references auth.users(id) on delete set null,
  feature text not null check (feature in ('photo', 'grading')),
  model text not null check (length(model) <= 100),
  input_tokens integer not null default 0 check (input_tokens >= 0),
  output_tokens integer not null default 0 check (output_tokens >= 0),
  cache_read_tokens integer not null default 0 check (cache_read_tokens >= 0),
  cache_write_tokens integer not null default 0 check (cache_write_tokens >= 0),
  cost_usd numeric(12, 6) not null default 0 check (cost_usd >= 0)
);
create index math_ai_usage_created on public.math_ai_usage(created_at);
alter table public.math_ai_usage enable row level security;
revoke all on public.math_ai_usage from public, anon, authenticated;
grant select, insert on public.math_ai_usage to service_role;
commit;
