-- Mathly 2: suggestions and feedback from the people who use the app (משוב, feedback.py). Additive, safe to run again.
-- Any signed-in person sends one (an idea, a problem or other, up to 2,000 characters) with the screen they were on; the developer reads
-- them and marks them handled. Read and written only by the server with the secret key, like every m2_ table.
-- Rollback: drop table public.m2_feedback;
begin;

create table if not exists public.m2_feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  email text not null,
  roles text[] not null default '{}',
  kind text not null check (kind in ('idea', 'bug', 'other')),
  body text not null check (char_length(body) between 1 and 2000),
  page text not null default '' check (char_length(page) <= 200),
  created_at timestamptz not null default now(),
  handled_at timestamptz
);
create index if not exists m2_feedback_created on public.m2_feedback (created_at desc);
create index if not exists m2_feedback_user on public.m2_feedback (user_id, created_at);

alter table public.m2_feedback enable row level security;
revoke all on public.m2_feedback from public, anon, authenticated;
grant all on public.m2_feedback to service_role;

commit;
