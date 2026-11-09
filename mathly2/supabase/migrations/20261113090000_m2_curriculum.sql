-- Mathly 2: the curriculum. One date per lesson for the whole school: the day by which the lesson should be completed.
-- A lesson without a row has no date. Lesson ids are the exercise bank's ids (text), as in m2_classes.lessons.
-- Additive (one new table). Rollback: drop table public.m2_curriculum;
begin;
create table public.m2_curriculum (
  lesson_id text primary key,
  due_date date not null
);
alter table public.m2_curriculum enable row level security;
revoke all on public.m2_curriculum from public, anon, authenticated;
grant all on public.m2_curriculum to service_role;
commit;
