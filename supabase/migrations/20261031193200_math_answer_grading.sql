-- Durable, owner-scoped checks of saved photos. No existing answers are changed.
begin;
create table public.math_answer_grades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  attempt_id uuid not null,
  attachment_id uuid not null references public.math_answer_attachments(id) on delete cascade,
  state text not null check (state in ('grading','completed','failed')),
  lease_id uuid not null,
  lease_until timestamptz not null,
  result jsonb,
  error text not null default '',
  created_at timestamptz not null default clock_timestamp(),
  finished_at timestamptz,
  foreign key (attempt_id,user_id) references public.math_question_attempts(id,user_id) on delete cascade,
  check ((state='completed') = (result is not null)),
  check (result is null or (jsonb_typeof(result)='object' and result ? 'verdict'
    and result->>'verdict' in ('correct','partial','incorrect','unreadable','needs_review')))
);
create index math_grade_attempt on public.math_answer_grades(attempt_id,created_at desc,id desc);
create index math_grade_daily on public.math_answer_grades(user_id,created_at);
create unique index math_grade_one_running on public.math_answer_grades(attachment_id) where state='grading';
alter table public.math_answer_grades enable row level security;
revoke all on public.math_answer_grades from public,anon,authenticated;
-- Read through the owner-checked backend; coordination tokens remain server-only.
grant all on public.math_answer_grades to service_role;

create function public.math_grade_action(p_user uuid,p_action text,p_data jsonb default '{}')
returns jsonb language plpgsql security invoker set search_path='' as $$
declare
  a public.math_question_attempts;
  att public.math_answer_attachments;
  g public.math_answer_grades;
  t timestamptz;
begin
  if p_user is null then raise exception 'not_found' using errcode='P0002'; end if;
  if p_action='start' then
    -- Serialize quota checks across this account, including distinct attempts/workers.
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('grading:'||p_user::text,0));
  end if;
  select * into a from public.math_question_attempts
    where id=(p_data->>'attempt_id')::uuid and user_id=p_user for update;
  if a.id is null then raise exception 'not_found' using errcode='P0002'; end if;
  select * into att from public.math_answer_attachments where attempt_id=a.id and user_id=p_user;
  select * into g from public.math_answer_grades where attempt_id=a.id
    order by created_at desc,id desc limit 1 for update;
  t := clock_timestamp();
  if g.state='grading' and g.lease_until<=t then
    update public.math_answer_grades set state='failed',error='grading_interrupted',finished_at=t
      where id=g.id returning * into g;
  end if;
  if p_action='start' then
    if att.id is null then raise exception 'answer_required' using errcode='P0001'; end if;
    -- Repeated clicks and lost responses reuse a running or completed check.
    if g.id is null or g.state='failed' then
      if (select count(*) from public.math_answer_grades where user_id=p_user
          and created_at >= ((t at time zone 'Asia/Jerusalem')::date::timestamp at time zone 'Asia/Jerusalem')) >= 20 then
        raise exception 'grading_limit' using errcode='P0001';
      end if;
      if (select count(*) from public.math_answer_grades where user_id=p_user
          and state='grading' and lease_until>t) >= 2 then
        raise exception 'grading_busy' using errcode='P0001';
      end if;
      insert into public.math_answer_grades(user_id,attempt_id,attachment_id,state,lease_id,lease_until)
        values(p_user,a.id,att.id,'grading',(p_data->>'lease_id')::uuid,t+interval '5 minutes') returning * into g;
    end if;
  elsif p_action in ('complete','fail') then
    if g.state is distinct from 'grading' or g.lease_id is distinct from (p_data->>'lease_id')::uuid then
      raise exception 'grading_interrupted' using errcode='P0001';
    end if;
    if p_action='complete' then
      update public.math_answer_grades set state='completed',result=p_data->'result',finished_at=t,error=''
        where id=g.id returning * into g;
    else
      update public.math_answer_grades set state='failed',finished_at=t,error='grading_failed'
        where id=g.id returning * into g;
    end if;
  elsif p_action<>'get' then
    raise exception 'invalid_action';
  end if;
  return case when g.id is null then null else to_jsonb(g) end;
end $$;
revoke all on function public.math_grade_action(uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.math_grade_action(uuid,text,jsonb) to service_role;
commit;
