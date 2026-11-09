-- Mathly 2: written work. Additive (new objects only). Read and written only by the server with the secret key: row-level security is on,
-- there are no policies, and the browser roles get no grants (as in m2_classes).
-- Pictures are not stored here: m2_pictures holds their rows, the bytes are in the private Storage bucket (MATHLY_M2_ANSWER_BUCKET, default m2-answers),
-- which the server creates on first use.
-- Rollback: drop table m2_push_subscriptions, m2_photo_requests, m2_submissions, m2_assignments, m2_pictures;
begin;

-- A picture: a page of an assignment (kind 'page') or a student's answer ('answer'). `deleted_at` is set when its bytes are removed.
create table public.m2_pictures (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  kind text not null check (kind in ('page', 'answer')),
  path text not null unique,
  content_type text not null,
  size integer not null check (size between 1 and 10000000),
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);
create index m2_pictures_owner on public.m2_pictures (owner_id);

-- Work a teacher gives a class: pages (pictures), one of the bank's written quizzes, or an exercise test of a real test.
create table public.m2_assignments (
  id bigint generated always as identity primary key,
  class_id bigint not null references public.m2_classes(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 200),
  note text not null default '',
  due_date date not null,
  kind text not null check (kind in ('pages', 'quiz', 'exercise_test')),
  pages uuid[] not null default '{}',
  quiz_lesson text,
  test_id bigint references public.m2_tests(id) on delete cascade,
  exercise_number integer check (exercise_number in (1, 2)),
  created_by text not null,
  created_at timestamptz not null default now(),
  removed_at timestamptz,
  check (case kind when 'pages' then cardinality(pages) > 0
                   when 'quiz' then quiz_lesson is not null
                   else test_id is not null and exercise_number is not null end)
);
create index m2_assignments_class on public.m2_assignments (class_id) where removed_at is null;

-- What a student handed in: one row per student and assignment, rewritten when they hand in again after a return.
create table public.m2_submissions (
  id bigint generated always as identity primary key,
  assignment_id bigint not null references public.m2_assignments(id) on delete cascade,
  user_id uuid not null,
  pictures uuid[] not null default '{}',
  state text not null default 'handed_in' check (state in ('handed_in', 'graded', 'returned')),
  late boolean not null default false,
  handed_at timestamptz not null default now(),
  grade integer check (grade between 0 and 100),
  teacher_note text not null default '',
  checked_at timestamptz,
  checked_by text,
  unique (assignment_id, user_id),
  check (state <> 'graded' or grade is not null)
);

-- A computer asking the student's phone for a photo of one answer.
create table public.m2_photo_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  assignment_id bigint not null references public.m2_assignments(id) on delete cascade,
  device text not null,
  code text not null check (code ~ '^[0-9]{4}$'),
  state text not null default 'waiting' check (state in ('waiting', 'uploading', 'received', 'failed', 'expired', 'superseded')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  picture_id uuid references public.m2_pictures(id) on delete set null,
  check (expires_at > created_at)
);
create index m2_photo_requests_user on public.m2_photo_requests (user_id, created_at);

-- A phone that turned notifications on. `key_id` is a fingerprint of the server's push key: a subscription made under another key is dropped.
create table public.m2_push_subscriptions (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  endpoint text not null unique,
  p256dh text not null,
  auth text not null,
  key_id text not null,
  created_at timestamptz not null default now()
);
create index m2_push_subscriptions_user on public.m2_push_subscriptions (user_id);

alter table public.m2_pictures enable row level security;
alter table public.m2_assignments enable row level security;
alter table public.m2_submissions enable row level security;
alter table public.m2_photo_requests enable row level security;
alter table public.m2_push_subscriptions enable row level security;
revoke all on public.m2_pictures, public.m2_assignments, public.m2_submissions, public.m2_photo_requests, public.m2_push_subscriptions from public, anon, authenticated;
grant all on public.m2_pictures, public.m2_assignments, public.m2_submissions, public.m2_photo_requests, public.m2_push_subscriptions to service_role;
grant usage, select on sequence public.m2_assignments_id_seq, public.m2_submissions_id_seq, public.m2_push_subscriptions_id_seq to service_role;
commit;
