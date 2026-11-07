-- Mathly 2: classes and their students. Additive (new tables only). Read and written only by the server with
-- the secret key: row-level security is on, there are no policies, and the browser roles get no grants.
begin;
create table public.m2_classes (
  id bigint generated always as identity primary key,
  name text not null check (char_length(name) between 1 and 60),
  teacher_email text not null check (teacher_email = lower(teacher_email)),
  created_at timestamptz not null default now()
);
create unique index m2_classes_teacher_name on public.m2_classes (teacher_email, lower(name));

-- A student belongs to one class at a time: the email is unique. user_id is filled at the student's first sign-in.
create table public.m2_class_members (
  class_id bigint not null references public.m2_classes(id) on delete cascade,
  email text primary key check (email = lower(email) and char_length(email) between 3 and 254),
  user_id uuid,
  added_at timestamptz not null default now()
);
create index m2_class_members_class on public.m2_class_members (class_id);
create index m2_class_members_user on public.m2_class_members (user_id) where user_id is not null;

alter table public.m2_classes enable row level security;
alter table public.m2_class_members enable row level security;
revoke all on public.m2_classes, public.m2_class_members from public, anon, authenticated;
grant all on public.m2_classes, public.m2_class_members to service_role;
commit;
