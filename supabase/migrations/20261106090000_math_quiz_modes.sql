-- Practice and final unit quizzes (app/quiz_modes.py). A practice sitting is what every sitting was until now: any
-- number, the clock kept by the page. A final sitting is given once, in a window the class teacher opens, with its
-- start time and deadline kept here. Additive: existing sittings become practice sittings, nothing else changes.
-- Apply after the quiz-sitting and teacher-review migrations: it rewrites two of their functions.
begin;

-- a final quiz of one unit, open to one class between two times; its results reach students once released
create table public.math_quiz_windows (
  id uuid primary key default gen_random_uuid(),
  class_id bigint not null references public.classes(id) on delete cascade,
  unit_id text not null check (char_length(unit_id) between 1 and 40),
  opens_at timestamptz not null,
  closes_at timestamptz not null,
  released_at timestamptz,
  created_by_email text not null default '',
  created_at timestamptz not null default now(),
  check (closes_at > opens_at)
);
create index math_quiz_windows_class on public.math_quiz_windows(class_id, unit_id, closes_at desc);

-- one more final sitting for one student (absent, a technical failure), until a time the teacher sets
create table public.math_quiz_grants (
  id uuid primary key default gen_random_uuid(),
  window_id uuid not null references public.math_quiz_windows(id) on delete cascade,
  student_id uuid not null,
  student_email text not null default '',
  until timestamptz not null,
  reason text not null default '' check (char_length(reason) <= 200),
  granted_by_email text not null default '',
  created_at timestamptz not null default now()
);
create index math_quiz_grants_student on public.math_quiz_grants(student_id, until desc);

-- a final sitting from the moment it starts: the server's clock, and the answer attempts in question order
create table public.math_quiz_starts (
  id uuid primary key default gen_random_uuid(),
  window_id uuid not null references public.math_quiz_windows(id) on delete cascade,
  grant_id uuid references public.math_quiz_grants(id) on delete cascade,
  user_id uuid not null,
  unit_id text not null,
  started_at timestamptz not null default now(),
  deadline timestamptz not null,
  attempt_ids uuid[] not null default '{}' check (cardinality(attempt_ids) <= 20),
  sitting_id uuid,
  check (deadline > started_at)
);
-- one final sitting per student and window, and one per grant
create unique index math_quiz_starts_once on public.math_quiz_starts(window_id, user_id) where grant_id is null;
create unique index math_quiz_starts_grant on public.math_quiz_starts(grant_id) where grant_id is not null;
create index math_quiz_starts_user on public.math_quiz_starts(user_id, started_at desc);
create index math_quiz_starts_attempts on public.math_quiz_starts using gin(attempt_ids);

alter table public.math_quiz_sittings
  add column mode text not null default 'practice' check (mode in ('practice', 'final')),
  add column started_at timestamptz,
  add column window_id uuid;   -- the window the server checked at hand-in (app/quiz_modes.py); kept if it goes

alter table public.math_quiz_windows enable row level security;
alter table public.math_quiz_grants enable row level security;
alter table public.math_quiz_starts enable row level security;
revoke all on public.math_quiz_windows, public.math_quiz_grants, public.math_quiz_starts from public, anon, authenticated;
grant all on public.math_quiz_windows, public.math_quiz_grants, public.math_quiz_starts to service_role;

-- the sitting also says which kind it is, when it started (final) and its window
create or replace function public.math_quiz_sitting_json(p_id uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
  select jsonb_build_object('id', s.id, 'user_id', s.user_id, 'unit_id', s.unit_id,
    'submitted_at', s.submitted_at, 'time_up', s.time_up,
    'mode', s.mode, 'started_at', s.started_at, 'window_id', s.window_id,
    'attempts', (select coalesce(jsonb_agg(jsonb_build_object(
        'attempt_id', x.aid, 'question_id', a.question_id, 'has_photo', att.id is not null,
        'grade_state', g.state, 'score', g.result->'score', 'verdict', g.result->>'verdict',
        'teacher_score', (select r.score from public.math_teacher_reviews r where r.attempt_id = x.aid
                          order by r.created_at desc, r.id desc limit 1)) order by x.ord), '[]'::jsonb)
      from unnest(s.attempt_ids) with ordinality as x(aid, ord)
      left join public.math_question_attempts a on a.id = x.aid
      left join public.math_answer_attachments att on att.attempt_id = x.aid
      left join lateral (select state, result from public.math_answer_grades
        where attempt_id = x.aid order by created_at desc, id desc limit 1) g on true))
  from public.math_quiz_sittings s where s.id = p_id
$$;

-- `submit` also stores the mode, start time and window the server checked (app/quiz_modes.py)
create or replace function public.math_quiz_action(p_user uuid, p_action text, p_data jsonb default '{}')
returns jsonb language plpgsql security invoker set search_path='' as $$
declare
  s public.math_quiz_sittings;
  ids uuid[];
  bad int;
begin
  if p_action = 'report' then   -- the class report: the latest sittings of these accounts
    return coalesce((select jsonb_agg(public.math_quiz_sitting_json(r.id) order by r.submitted_at) from (
      select q.id, q.submitted_at, row_number() over (partition by q.user_id, q.unit_id
                                                      order by q.submitted_at desc, q.id desc) as rn
      from public.math_quiz_sittings q
      where q.user_id in (select t.x::uuid from jsonb_array_elements_text(p_data->'users') as t(x))) r
      where r.rn <= 10), '[]'::jsonb);
  end if;
  if p_user is null then raise exception 'not_found' using errcode = 'P0002'; end if;
  if p_action = 'list' then
    return coalesce((select jsonb_agg(public.math_quiz_sitting_json(r.id) order by r.submitted_at desc) from (
      select q.id, q.submitted_at from public.math_quiz_sittings q
      where q.user_id = p_user and (p_data->>'unit_id' is null or q.unit_id = p_data->>'unit_id')
      order by q.submitted_at desc, q.id desc limit 10) r), '[]'::jsonb);
  elsif p_action = 'submit' then
    -- the same submit again (a lost response) is the same sitting
    select * into s from public.math_quiz_sittings
      where user_id = p_user and client_key = (p_data->>'client_key')::uuid;
    if s.id is not null then return public.math_quiz_sitting_json(s.id); end if;
    ids := array(select t.x::uuid from jsonb_array_elements_text(p_data->'attempt_ids') with ordinality as t(x, o) order by t.o);
    -- every attempt is the student's own, for the quiz question at its position
    select count(*) into bad from unnest(ids) with ordinality as x(aid, o)
      left join public.math_question_attempts a on a.id = x.aid and a.user_id = p_user
      where a.id is null or a.question_id <> 'quiz:' || (p_data->>'unit_id') || ':' || (x.o - 1);
    if bad > 0 or exists(select 1 from public.math_quiz_sittings where user_id = p_user and attempt_ids && ids) then
      raise exception 'invalid_sitting' using errcode = 'P0001';
    end if;
    insert into public.math_quiz_sittings(user_id, unit_id, attempt_ids, time_up, client_key, mode, started_at, window_id)
      values (p_user, p_data->>'unit_id', ids, coalesce((p_data->>'time_up')::boolean, false), (p_data->>'client_key')::uuid,
              coalesce(p_data->>'mode', 'practice'), (p_data->>'started_at')::timestamptz, (p_data->>'window_id')::uuid)
      returning * into s;
    return public.math_quiz_sitting_json(s.id);
  end if;
  raise exception 'invalid_action';
end $$;
commit;
