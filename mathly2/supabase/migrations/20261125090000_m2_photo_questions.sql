-- Mathly 2: photographed questions (שאלה מצולמת, photoq.py). A student photographs a question with the phone (the 4-digit code, as for
-- an assignment); the AI reads it, suggests its skill (or "external") and keeps its answer for the check; the student answers it on the
-- board; the AI gives a grade 0-100 and feedback on the way. The class's teacher approves it into the class's bank (or rejects it), and
-- then the class's other students can solve it too. Server only, like every m2_ table. Safe to run again.
-- Rollback: drop table public.m2_photo_questions;
--           delete from public.m2_photo_requests where assignment_id is null;
--           alter table public.m2_photo_requests drop column purpose; alter table public.m2_photo_requests alter column assignment_id set not null;
begin;

-- A photo request for a question has no assignment.
alter table public.m2_photo_requests alter column assignment_id drop not null;
alter table public.m2_photo_requests add column if not exists purpose text not null default 'assignment';
alter table public.m2_photo_requests drop constraint if exists m2_photo_requests_purpose_check;
alter table public.m2_photo_requests add constraint m2_photo_requests_purpose_check
  check ((purpose = 'assignment' and assignment_id is not null) or (purpose = 'question' and assignment_id is null));

create table if not exists public.m2_photo_questions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  class_id bigint,
  subject_id text not null default 'math',
  picture_id uuid,                                          -- the photo (none for a question taken from the class's bank)
  source_id uuid references public.m2_photo_questions(id) on delete set null,
  state text not null default 'reading' check (state in ('reading', 'ready', 'unreadable', 'failed', 'checking', 'checked')),
  question text not null default '' check (char_length(question) <= 4000),
  answer text not null default '' check (char_length(answer) <= 1000),      -- the AI's answer: for the check, never shown to the student
  steps jsonb not null default '[]'::jsonb,
  suggested_skill text,                                     -- the AI's suggestion; null: external
  skill_id text,                                            -- the student's choice (or the teacher's); null: external
  typed text not null default '' check (char_length(typed) <= 40),
  grade integer check (grade between 0 and 100),
  review jsonb,                                             -- {verdict, feedback, tip}
  reason text,                                              -- why reading or checking failed
  bank text not null default 'none' check (bank in ('none', 'pending', 'approved', 'rejected')),
  decided_by text,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  checked_at timestamptz
);
create index if not exists m2_photo_questions_user on public.m2_photo_questions (user_id, created_at desc);
create index if not exists m2_photo_questions_class on public.m2_photo_questions (class_id, bank);

alter table public.m2_photo_questions enable row level security;
revoke all on public.m2_photo_questions from public, anon, authenticated;
grant all on public.m2_photo_questions to service_role;

commit;
