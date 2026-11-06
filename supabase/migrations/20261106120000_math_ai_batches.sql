-- AI checks of student work, for a whole class (app/ai_batches.py): a daily budget per class, taken atomically, so a
-- teacher can send a whole quiz or worksheet in one action without using their own 3 requests a day; batches of
-- requests; and the AI's suggestion kept on a worksheet submission until the teacher saves their check.
-- Additive. Apply after the AI-queue and worksheet migrations.
begin;
alter table public.classes
  add column if not exists ai_daily_checks integer check (ai_daily_checks is null or ai_daily_checks between 0 and 5000),
  add column if not exists auto_send_practice boolean not null default false;

create table public.math_class_ai_budget (
  class_id bigint not null references public.classes(id) on delete cascade,
  day date not null,
  used integer not null default 0 check (used >= 0),
  primary key (class_id, day)
);

create table public.math_ai_batches (
  id uuid primary key default gen_random_uuid(),
  class_id bigint not null references public.classes(id) on delete cascade,
  scope text not null check (char_length(scope) between 1 and 80),
  created_by_email text not null default '',
  total integer not null check (total >= 0),
  sent integer not null default 0 check (sent >= 0),
  created_at timestamptz not null default now()
);
create index math_ai_batches_class on public.math_ai_batches(class_id, created_at desc);

alter table public.math_ai_requests add column if not exists batch_id uuid;

alter table public.math_worksheet_submissions
  add column if not exists ai_score integer check (ai_score between 0 and 100),
  add column if not exists ai_comment text not null default '' check (char_length(ai_comment) <= 1000),
  add column if not exists ai_readable boolean,
  add column if not exists ai_checked_at timestamptz;

-- takes up to p_n checks from the class's budget for the day, never past p_limit; the number granted
create function public.math_take_class_checks(p_class bigint, p_day date, p_n integer, p_limit integer)
returns integer language plpgsql security invoker set search_path='' as $$
declare
  have integer;
  granted integer;
begin
  insert into public.math_class_ai_budget(class_id, day, used) values (p_class, p_day, 0) on conflict do nothing;
  select used into have from public.math_class_ai_budget where class_id = p_class and day = p_day for update;
  granted := least(greatest(p_n, 0), greatest(p_limit - have, 0));
  update public.math_class_ai_budget set used = have + granted where class_id = p_class and day = p_day;
  return granted;
end $$;

-- gives back checks that failed or could not read the photo
create function public.math_give_class_checks(p_class bigint, p_day date, p_n integer)
returns integer language sql security invoker set search_path='' as $$
  update public.math_class_ai_budget set used = greatest(used - greatest(p_n, 0), 0)
  where class_id = p_class and day = p_day returning used
$$;

alter table public.math_class_ai_budget enable row level security;
alter table public.math_ai_batches enable row level security;
revoke all on public.math_class_ai_budget, public.math_ai_batches from public, anon, authenticated;
grant all on public.math_class_ai_budget, public.math_ai_batches to service_role;
revoke all on function public.math_take_class_checks(bigint, date, integer, integer) from public, anon, authenticated;
revoke all on function public.math_give_class_checks(bigint, date, integer) from public, anon, authenticated;
grant execute on function public.math_take_class_checks(bigint, date, integer, integer) to service_role;
grant execute on function public.math_give_class_checks(bigint, date, integer) to service_role;
commit;
