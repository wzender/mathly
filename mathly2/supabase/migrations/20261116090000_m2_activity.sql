-- Mathly 2: activity for the developer's status card (PRD DEV-5). Additive (one view, one index).
-- One row per person and Israel calendar day on which they practised or started a quiz or test: how many practice answers
-- and how many attempts. Read only by the server with the secret key, like the tables it reads.
-- Rollback: drop view m2_activity; drop index m2_answers_day;
begin;

create index if not exists m2_answers_day on public.m2_answers (day);

create view public.m2_activity as
  select day, user_id, sum(answers)::integer as answers, sum(attempts)::integer as attempts
  from (
    select day, user_id, 1 as answers, 0 as attempts from public.m2_answers
    union all
    select (started_at at time zone 'Asia/Jerusalem')::date as day, user_id, 0, 1 from public.m2_attempts
  ) as done
  group by day, user_id;

revoke all on public.m2_activity from public, anon, authenticated;
grant select on public.m2_activity to service_role;
commit;
