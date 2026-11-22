-- Mathly 2: each student's practice per Israel day, for the teacher's activity view (progress.py): practice answers (the exercise screen,
-- lesson rounds, rounds on the go, the review), right ones, and an estimate of the time spent. Time: within a day, the gap since the
-- previous answer counts up to 3 minutes; a gap of more than 5 minutes is a break, and the first answer after it (or of the day) counts
-- 1 minute. Server only, like every m2_ view. Safe to run again.
-- Rollback: drop view public.m2_daily_practice;
begin;

create or replace view public.m2_daily_practice as
  select user_id, day, count(*)::integer as answers, (count(*) filter (where correct))::integer as correct,
         sum(case when gap is null or gap > 300 then 60 else least(gap, 180) end)::integer as seconds
  from (
    select user_id, day, correct,
           extract(epoch from answered_at - lag(answered_at) over (partition by user_id, day order by answered_at, id)) as gap
    from public.m2_answers
  ) as timed
  group by user_id, day;

revoke all on public.m2_daily_practice from public, anon, authenticated;
grant select on public.m2_daily_practice to service_role;

commit;
