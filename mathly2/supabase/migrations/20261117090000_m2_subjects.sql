-- Mathly 2: subjects and lessons kept in the database (change add-subjects-and-worksheets). Additive.
-- A subject owns lessons. Math is a subject from the start and owns every unit of the math content file; lessons of other
-- subjects (and lessons added to math) are rows of m2_lessons. A lesson row holds its editable `draft` and, once published,
-- the `published` copy that students get: both are one unit in the content file's shape. The worksheet a lesson was drafted
-- from is kept as files in the private Storage bucket m2-worksheets (made by the server when first needed).
-- Classes study subjects (math by default) and tests belong to one subject (math by default), so existing rows read as math.
-- Read and written only by the server with the secret key, like every m2_ table.
-- Rollback: alter table m2_tests drop column subject_id; alter table m2_classes drop column subjects; drop table m2_lessons, m2_subjects;
begin;

create table public.m2_subjects (
  id text primary key check (id ~ '^[a-z0-9_]{1,40}$'),
  name text not null check (char_length(name) between 1 and 60),
  icon text not null default '∑' check (char_length(icon) between 1 and 8),
  position integer not null default 0,
  created_by text not null default 'setup',
  created_at timestamptz not null default now()
);
create unique index m2_subjects_name on public.m2_subjects (lower(name));
insert into public.m2_subjects (id, name, icon, position) values ('math', 'מתמטיקה', '∑', 0) on conflict (id) do nothing;

create table public.m2_lessons (
  id bigint generated always as identity primary key,
  subject_id text not null references public.m2_subjects(id),
  position integer not null default 0,
  draft jsonb not null default '{}',
  published jsonb,                                     -- null: not published (a draft only)
  status text not null default 'ready' check (status in ('drafting', 'ready', 'failed')),
  failure text,                                        -- why drafting failed, for the uploader
  files jsonb not null default '[]',                   -- the worksheet: [{"kind": "pdf"|"photo"|"docx"|"page", "path": ...}]
  source text not null default 'json' check (source in ('json', 'worksheet')),
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz
);
create index m2_lessons_subject on public.m2_lessons (subject_id, position);
create index m2_lessons_published on public.m2_lessons (id) where published is not null;

alter table public.m2_classes add column if not exists subjects text[] not null default '{math}';
alter table public.m2_tests add column if not exists subject_id text not null default 'math';

alter table public.m2_subjects enable row level security;
alter table public.m2_lessons enable row level security;
revoke all on public.m2_subjects, public.m2_lessons from public, anon, authenticated;
grant all on public.m2_subjects, public.m2_lessons to service_role;
grant usage, select on sequence public.m2_lessons_id_seq to service_role;
commit;
