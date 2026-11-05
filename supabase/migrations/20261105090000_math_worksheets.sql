-- Worksheets a class teacher attaches to an assignment, and the students' photographed solutions (app/worksheets.py).
-- Additive: two new tables and a private bucket, read and written only with the server's secret key.
begin;
create table public.math_worksheets (
  id uuid primary key default gen_random_uuid(),
  class_id bigint not null references public.classes(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 80),
  source text not null check (source in ('pdf','images')),
  pages integer not null check (pages between 1 and 10),
  original_key text,
  page_keys text[] not null check (cardinality(page_keys) between 1 and 10),
  byte_size integer not null check (byte_size > 0),
  created_by_email text not null default '',
  created_at timestamptz not null default now(),
  check (cardinality(page_keys) = pages),
  check ((source = 'pdf') = (original_key is not null))
);
create index math_worksheets_class on public.math_worksheets(class_id, created_at desc);

create table public.math_worksheet_submissions (
  id uuid primary key default gen_random_uuid(),
  worksheet_id uuid not null references public.math_worksheets(id) on delete cascade,
  student_id uuid not null,
  student_email text not null default '',
  page_keys text[] not null check (cardinality(page_keys) between 1 and 10),
  submitted_at timestamptz not null default now(),
  checked_at timestamptz,
  score integer check (score between 0 and 100),
  comment text not null default '' check (char_length(comment) <= 1000),
  checked_by_email text not null default '',
  unique (worksheet_id, student_id)
);
create index math_worksheet_submissions_student on public.math_worksheet_submissions(student_id);

alter table public.math_worksheets enable row level security;
alter table public.math_worksheet_submissions enable row level security;
revoke all on public.math_worksheets, public.math_worksheet_submissions from public, anon, authenticated;
grant all on public.math_worksheets, public.math_worksheet_submissions to service_role;

insert into storage.buckets(id, name, public, file_size_limit, allowed_mime_types)
  values ('mathly-worksheets', 'mathly-worksheets', false, 10000000, array['image/jpeg','application/pdf']);
-- Restrictive, so a permissive "all buckets" policy cannot open it.
create policy math_worksheet_private on storage.objects as restrictive for all to anon, authenticated
  using (bucket_id <> 'mathly-worksheets') with check (bucket_id <> 'mathly-worksheets');
commit;
