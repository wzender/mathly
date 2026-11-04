-- The class teacher's review of a student's checked open answer (app/teacher_review.py): a score of their own and a
-- comment, and the student's request to look again. Additive: two tables and two functions, and the quiz-sitting
-- function now also reads the teacher's score. Apply after the quiz-sittings migration.
begin;
create table public.math_teacher_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,      -- the student
  attempt_id uuid not null,
  reviewer_email text not null,
  score integer check (score between 0 and 100),
  comment text not null default '' check (char_length(comment) <= 1000),
  created_at timestamptz not null default clock_timestamp(),
  seen_at timestamptz,                                                    -- when the student opened the answer after it
  foreign key (attempt_id, user_id) references public.math_question_attempts(id, user_id) on delete cascade,
  check (score is not null or comment <> '')
);
-- a newer review replaces the older one: the latest of an attempt counts, the rest is history
create index math_teacher_reviews_attempt on public.math_teacher_reviews(attempt_id, created_at desc, id desc);
create index math_teacher_reviews_unseen on public.math_teacher_reviews(user_id) where seen_at is null;

create table public.math_review_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  attempt_id uuid not null,
  message text not null default '' check (char_length(message) <= 300),
  state text not null default 'open' check (state in ('open', 'closed')),
  created_at timestamptz not null default clock_timestamp(),
  closed_at timestamptz,
  foreign key (attempt_id, user_id) references public.math_question_attempts(id, user_id) on delete cascade
);
create unique index math_review_one_open on public.math_review_requests(attempt_id) where state = 'open';
create index math_review_requests_open on public.math_review_requests(user_id) where state = 'open';
alter table public.math_teacher_reviews enable row level security;
alter table public.math_review_requests enable row level security;
revoke all on public.math_teacher_reviews, public.math_review_requests from public, anon, authenticated;
grant all on public.math_teacher_reviews, public.math_review_requests to service_role;

-- an attempt's latest review and latest request
create function public.math_review_json(p_attempt uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
  select jsonb_build_object(
    'review', (select to_jsonb(r) from (select id, reviewer_email, score, comment, created_at, seen_at
      from public.math_teacher_reviews where attempt_id = p_attempt order by created_at desc, id desc limit 1) r),
    'request', (select to_jsonb(q) from (select id, message, state, created_at, closed_at
      from public.math_review_requests where attempt_id = p_attempt order by created_at desc, id desc limit 1) q))
$$;

create function public.math_review_action(p_user uuid, p_action text, p_data jsonb default '{}')
returns jsonb language plpgsql security invoker set search_path='' as $$
declare
  a public.math_question_attempts;
  q public.math_review_requests;
begin
  if p_action = 'owner' then   -- whose answer this is (the teacher's routes then act as the student)
    select * into a from public.math_question_attempts where id = (p_data->>'attempt_id')::uuid;
    if a.id is null then raise exception 'not_found' using errcode = 'P0002'; end if;
    return to_jsonb(a.user_id);
  elsif p_action = 'requests' then   -- open requests to look again; `users` null: everyone's
    return coalesce((select jsonb_agg(jsonb_build_object('id', r.id, 'attempt_id', r.attempt_id, 'user_id', r.user_id,
        'message', r.message, 'created_at', r.created_at, 'question', coalesce(t.snapshot->>'name', left(t.snapshot->>'question', 80)), 'question_id', t.question_id)
        order by r.created_at)
      from public.math_review_requests r
      join public.math_question_attempts t on t.id = r.attempt_id and t.user_id = r.user_id
      where r.state = 'open' and (p_data->'users' is null
        or r.user_id in (select u.x::uuid from jsonb_array_elements_text(p_data->'users') as u(x)))), '[]'::jsonb);
  end if;
  if p_user is null then raise exception 'not_found' using errcode = 'P0002'; end if;
  if p_action = 'unseen' then   -- reviews the student has not opened since
    return coalesce((select jsonb_agg(jsonb_build_object('attempt_id', r.attempt_id, 'question', coalesce(t.snapshot->>'name', left(t.snapshot->>'question', 80)),
        'question_id', t.question_id, 'score', r.score, 'comment', r.comment, 'created_at', r.created_at)
        order by r.created_at desc)
      from (select distinct on (attempt_id) * from public.math_teacher_reviews where user_id = p_user
            order by attempt_id, created_at desc, id desc) r
      join public.math_question_attempts t on t.id = r.attempt_id and t.user_id = r.user_id
      where r.seen_at is null), '[]'::jsonb);
  end if;
  select * into a from public.math_question_attempts where id = (p_data->>'attempt_id')::uuid and user_id = p_user;
  if a.id is null then raise exception 'not_found' using errcode = 'P0002'; end if;
  if p_action = 'get' then
    return public.math_review_json(a.id);
  elsif p_action = 'seen' then
    update public.math_teacher_reviews set seen_at = clock_timestamp() where attempt_id = a.id and seen_at is null;
    return public.math_review_json(a.id);
  elsif p_action in ('review', 'request') then
    if not exists(select 1 from public.math_answer_attachments where attempt_id = a.id) then
      raise exception 'answer_required' using errcode = 'P0001';
    end if;
    if p_action = 'review' then
      insert into public.math_teacher_reviews(user_id, attempt_id, reviewer_email, score, comment)
        values (p_user, a.id, p_data->>'reviewer', (p_data->>'score')::int, coalesce(p_data->>'comment', ''));
      update public.math_review_requests set state = 'closed', closed_at = clock_timestamp()
        where attempt_id = a.id and state = 'open';
    else
      select * into q from public.math_review_requests where attempt_id = a.id and state = 'open';
      if q.id is null then
        -- serialize this student's requests, so the limit holds across workers
        perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('review:' || p_user::text, 0));
        if (select count(*) from public.math_review_requests where user_id = p_user and state = 'open') >= 5 then
          raise exception 'review_limit' using errcode = 'P0001';
        end if;
        insert into public.math_review_requests(user_id, attempt_id, message)
          values (p_user, a.id, coalesce(p_data->>'message', ''));
      end if;
    end if;
    return public.math_review_json(a.id);
  end if;
  raise exception 'invalid_action';
end $$;
revoke all on function public.math_review_json(uuid) from public, anon, authenticated;
revoke all on function public.math_review_action(uuid, text, jsonb) from public, anon, authenticated;
grant execute on function public.math_review_json(uuid) to service_role;
grant execute on function public.math_review_action(uuid, text, jsonb) to service_role;

-- the quiz sitting also carries each answer's teacher score, so its grade can use it (app/quiz_grades.py)
create or replace function public.math_quiz_sitting_json(p_id uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
  select jsonb_build_object('id', s.id, 'user_id', s.user_id, 'unit_id', s.unit_id,
    'submitted_at', s.submitted_at, 'time_up', s.time_up,
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
commit;
