-- Mathly 2: the AI tutor's conversations on practice questions (practice_tutor.py), for the class's teacher to read. One row a student,
-- question and day; each message to the tutor adds the student's message and the reply to `messages`. The daily limit is counted here.
-- Safe to run again. Rollback: drop table public.m2_tutor_chats;
begin;

create table if not exists public.m2_tutor_chats (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  skill_id text not null,
  question_key text not null,
  day date not null,
  messages jsonb not null default '[]'::jsonb,              -- [{role: student|ai, text, at}]
  helped boolean not null default false,                    -- asked before answering: that answer did not count for mastery
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, skill_id, question_key, day)
);
create index if not exists m2_tutor_chats_user_day on public.m2_tutor_chats (user_id, day desc);

alter table public.m2_tutor_chats enable row level security;
revoke all on public.m2_tutor_chats from public, anon, authenticated;
grant all on public.m2_tutor_chats to service_role;

commit;
