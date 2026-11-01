-- Lesson resources: photos teachers add to a unit. Additive; existing tables are untouched.
begin;
create table public.math_unit_resources (
  id uuid primary key default gen_random_uuid(),
  unit_id text not null,
  kind text not null check (kind in ('exercise','theory','other')),
  note text not null default '' check (char_length(note) <= 200),
  skill_id text,
  object_key text not null unique,
  byte_size integer not null check (byte_size > 0 and byte_size <= 5000000),
  created_by uuid references auth.users(id) on delete set null,
  created_email text not null default '',
  created_at timestamptz not null default now(),
  check (kind <> 'other' or note <> '')
);
create index math_unit_resources_unit on public.math_unit_resources(unit_id, created_at desc);
alter table public.math_unit_resources enable row level security;
-- Only the backend (service role) reads or writes; it checks the teacher first.
revoke all on public.math_unit_resources from anon, authenticated;
grant all on public.math_unit_resources to service_role;

insert into storage.buckets(id, name, public, file_size_limit, allowed_mime_types)
  values ('mathly-resources', 'mathly-resources', false, 5000000, array['image/jpeg']);
-- Restrictive, so a permissive "all buckets" policy cannot open it.
create policy math_resource_private on storage.objects as restrictive for all to anon, authenticated
  using (bucket_id <> 'mathly-resources') with check (bucket_id <> 'mathly-resources');
commit;
