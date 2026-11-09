-- Mathly 2: AI help. A request is a student's photographed problem ('photo'), an AI check of a handed-in answer ('check') or a student asking the
-- teacher to look again ('again', no AI call). The teacher sends or declines it. The result, the teacher's note and a failure record are columns.
-- Budgets are rows taken in one step by m2_ai_take (scope 'class:<id>' or 'teacher:<email>', one row per Israel day); m2_ai_usage keeps every call's cost.
-- Additive, plus one widened check on m2_pictures.kind. No policies and no browser grants, as in the other m2_ tables.
-- Rollback: drop function public.m2_ai_give_back(text, date, integer); drop function public.m2_ai_take(text, date, integer, integer);
--           drop table public.m2_ai_usage, public.m2_ai_allowance, public.m2_ai_requests;
--           alter table public.m2_pictures drop constraint m2_pictures_kind_check; alter table public.m2_pictures add constraint m2_pictures_kind_check check (kind in ('page', 'answer'));
begin;

alter table public.m2_pictures drop constraint m2_pictures_kind_check;
alter table public.m2_pictures add constraint m2_pictures_kind_check check (kind in ('page', 'answer', 'help'));

create table public.m2_ai_requests (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('photo', 'check', 'again')),
  user_id uuid not null,
  class_id bigint references public.m2_classes(id) on delete cascade,          -- null: a teacher's or developer's own request
  state text not null default 'waiting' check (state in ('waiting', 'processing', 'done', 'failed', 'declined', 'cancelled', 'closed')),
  picture_id uuid references public.m2_pictures(id) on delete set null,
  assignment_id bigint references public.m2_assignments(id) on delete cascade,
  skill_id text,
  snapshot jsonb,
  result jsonb,
  teacher_note text not null default '',
  failure jsonb,
  budget jsonb,                                                                  -- what was taken for it (scope, day, n), to give back
  sent_by text,
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  done_at timestamptz,
  check (kind <> 'photo' or picture_id is not null or state in ('declined', 'cancelled', 'done', 'failed')),
  check (kind = 'photo' or assignment_id is not null),
  check (kind <> 'again' or class_id is not null)
);
create index m2_ai_requests_class_state on public.m2_ai_requests (class_id, state, created_at);
create index m2_ai_requests_user on public.m2_ai_requests (user_id, created_at);

create table public.m2_ai_allowance (
  scope text not null,
  day date not null,
  used integer not null default 0 check (used >= 0),
  primary key (scope, day)
);

-- Take n from the day's allowance only if it stays within the cap; true when taken. One statement, so two callers at once never pass the cap.
create function public.m2_ai_take(p_scope text, p_day date, p_n integer, p_cap integer) returns boolean
language plpgsql as $$
begin
  insert into public.m2_ai_allowance (scope, day, used) values (p_scope, p_day, 0) on conflict do nothing;
  update public.m2_ai_allowance set used = used + p_n where scope = p_scope and day = p_day and used + p_n <= p_cap;
  return found;
end $$;

create function public.m2_ai_give_back(p_scope text, p_day date, p_n integer) returns void
language sql as $$
  update public.m2_ai_allowance set used = greatest(used - p_n, 0) where scope = p_scope and day = p_day;
$$;

create table public.m2_ai_usage (
  id bigint generated always as identity primary key,
  request_id uuid,
  user_id uuid,
  feature text not null check (feature in ('photo', 'check')),
  model text not null,
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  cache_read_tokens integer not null default 0,
  cache_write_tokens integer not null default 0,
  cost_usd numeric(12, 6) not null default 0,
  created_at timestamptz not null default now()
);
create index m2_ai_usage_created on public.m2_ai_usage (created_at);

alter table public.m2_ai_requests enable row level security;
alter table public.m2_ai_allowance enable row level security;
alter table public.m2_ai_usage enable row level security;
revoke all on public.m2_ai_requests, public.m2_ai_allowance, public.m2_ai_usage from public, anon, authenticated;
revoke execute on function public.m2_ai_take(text, date, integer, integer) from public, anon, authenticated;
revoke execute on function public.m2_ai_give_back(text, date, integer) from public, anon, authenticated;
grant all on public.m2_ai_requests, public.m2_ai_allowance, public.m2_ai_usage to service_role;
grant usage, select on sequence public.m2_ai_usage_id_seq to service_role;
grant execute on function public.m2_ai_take(text, date, integer, integer) to service_role;
grant execute on function public.m2_ai_give_back(text, date, integer) to service_role;
commit;
