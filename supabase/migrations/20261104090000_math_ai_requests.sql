-- The teacher's AI queue (app/ai_queue.py): a student does not call Claude. Their photographed problem, or the answer
-- they want checked, waits here until their class's teacher (or a manager) looks at it and sends it to the AI or
-- declines it. Additive: one new table; nothing existing changes. Only the server's secret key reads or writes it.
begin;
create table public.math_ai_requests (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  user_id uuid not null references auth.users(id) on delete cascade,
  email text not null check (length(email) <= 320),
  kind text not null check (kind in ('photo', 'grading')),
  state text not null default 'pending'
    check (state in ('pending', 'sending', 'done', 'failed', 'declined', 'cancelled')),
  attempt_id uuid,                              -- grading: the saved answer (math_question_attempts) to check
  label text not null default '' check (length(label) <= 300),        -- grading: the question's name
  question text not null default '' check (length(question) <= 4000), -- grading: the question, for the teacher
  image text check (length(image) <= 8000000),  -- photo: base64 JPEG; cleared once the request is handled
  result jsonb,                                 -- photo: the solution the student sees
  note text not null default '' check (length(note) <= 500),         -- the teacher's word when declining
  error text not null default '' check (length(error) <= 300),
  reviewed_by text not null default '' check (length(reviewed_by) <= 320),
  sent_at timestamptz,
  finished_at timestamptz,
  check ((kind = 'grading') = (attempt_id is not null))
);
create index math_ai_requests_queue on public.math_ai_requests(state, created_at);
create index math_ai_requests_mine on public.math_ai_requests(user_id, created_at desc);
-- one open request per answer: a second click finds the first
create unique index math_ai_requests_one_open on public.math_ai_requests(attempt_id)
  where state in ('pending', 'sending');
alter table public.math_ai_requests enable row level security;
revoke all on public.math_ai_requests from public, anon, authenticated;
grant select, insert, update, delete on public.math_ai_requests to service_role;
commit;
