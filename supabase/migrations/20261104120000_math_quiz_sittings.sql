-- Unit-quiz sittings kept on the server (app/quiz_grades.py), so a quiz grade comes from the stored checks and not
-- from the student's device. Additive: one new table and two functions; nothing existing changes.
-- Apply after the answer-scan and answer-grading migrations: the functions read their tables.
begin;
create table public.math_quiz_sittings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  unit_id text not null,
  attempt_ids uuid[] not null check (cardinality(attempt_ids) between 1 and 20),
  submitted_at timestamptz not null default now(),
  time_up boolean not null default false,
  client_key uuid not null,
  unique (user_id, client_key)
);
create index math_quiz_sittings_user on public.math_quiz_sittings(user_id, unit_id, submitted_at desc);
alter table public.math_quiz_sittings enable row level security;
revoke all on public.math_quiz_sittings from public, anon, authenticated;
grant all on public.math_quiz_sittings to service_role;

-- A sitting with what its grade is computed from: for each attempt in question order, whether it has a saved photo
-- and its latest check (state, score, verdict). The points per question are in the app's data, not here.
create function public.math_quiz_sitting_json(p_id uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
  select jsonb_build_object('id', s.id, 'user_id', s.user_id, 'unit_id', s.unit_id,
    'submitted_at', s.submitted_at, 'time_up', s.time_up,
    'attempts', (select coalesce(jsonb_agg(jsonb_build_object(
        'attempt_id', x.aid, 'question_id', a.question_id, 'has_photo', att.id is not null,
        'grade_state', g.state, 'score', g.result->'score', 'verdict', g.result->>'verdict') order by x.ord), '[]'::jsonb)
      from unnest(s.attempt_ids) with ordinality as x(aid, ord)
      left join public.math_question_attempts a on a.id = x.aid
      left join public.math_answer_attachments att on att.attempt_id = x.aid
      left join lateral (select state, result from public.math_answer_grades
        where attempt_id = x.aid order by created_at desc, id desc limit 1) g on true))
  from public.math_quiz_sittings s where s.id = p_id
$$;

create function public.math_quiz_action(p_user uuid, p_action text, p_data jsonb default '{}')
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
    insert into public.math_quiz_sittings(user_id, unit_id, attempt_ids, time_up, client_key)
      values (p_user, p_data->>'unit_id', ids, coalesce((p_data->>'time_up')::boolean, false), (p_data->>'client_key')::uuid)
      returning * into s;
    return public.math_quiz_sitting_json(s.id);
  end if;
  raise exception 'invalid_action';
end $$;
revoke all on function public.math_quiz_sitting_json(uuid) from public, anon, authenticated;
revoke all on function public.math_quiz_action(uuid, text, jsonb) from public, anon, authenticated;
grant execute on function public.math_quiz_sitting_json(uuid) to service_role;
grant execute on function public.math_quiz_action(uuid, text, jsonb) to service_role;
commit;
