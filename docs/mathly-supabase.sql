-- Destructive one-time migration from the former multi-product application.
-- Back up the project before running this file.
drop table if exists public.attempts cascade;
drop table if exists public.writings cascade;
drop table if exists public.tutors cascade;
drop table if exists public.flags cascade;
drop table if exists public.lab_samples cascade;
drop table if exists public.calibrations cascade;
drop table if exists public.scoring_rules cascade;
drop table if exists public.model_settings cascade;
drop table if exists public.videos cascade;
drop table if exists public.texts cascade;
drop table if exists public.dailies cascade;
drop table if exists public.library cascade;
drop table if exists public.learner_class_state cascade;
drop table if exists public.tutor_chats cascade;

-- Mathly owns only math-class rosters and role assignments.
create table if not exists public.classes (
  id bigint generated always as identity primary key,
  name text not null unique,
  emails text[] not null default '{}',
  nicknames jsonb not null default '{}',
  lessons text[] not null default '{}',
  teachers text[] not null default '{}',
  exams jsonb not null default '[]',
  exam_title text not null default '',
  exam_note text not null default '',
  created_at timestamptz not null default now()
);

alter table public.classes drop column if exists homework,
  drop column if exists due,
  drop column if exists homeworks,
  drop column if exists dailies;

create table if not exists public.user_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null default '',
  roles text[] not null default array['student']::text[],
  updated_at timestamptz not null default now()
);

alter table public.user_access drop column if exists subject,
  drop column if exists entitlements;

alter table public.classes enable row level security;
alter table public.user_access enable row level security;
revoke all on public.classes from anon, authenticated;
revoke all on public.user_access from anon, authenticated;
