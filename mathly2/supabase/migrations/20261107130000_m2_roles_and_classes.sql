-- Mathly 2: roles given by an admin, and classes made by a manager. Only m2_ objects change (mathly1's tables are never touched).
-- Rollback: drop function m2_take_role; drop table m2_roles; drop the two triggers and their functions; then restore the old
--   class key and the per-teacher name index (see the statements below, reversed) and drop the added m2_classes columns.
begin;

-- Roles belong to an email (so they can be given before a first sign-in). The developer role comes only from the app's settings.
create table public.m2_roles (
  email text not null check (email = lower(email) and char_length(email) between 3 and 254),
  role text not null check (role in ('student', 'teacher', 'manager', 'admin')),
  granted_by text,
  granted_at timestamptz not null default now(),
  primary key (email, role)
);

-- Classes: a manager creates them. teacher_email used to mean "who created it"; now it is the class's teacher (optional).
alter table public.m2_classes add column created_by text;
update public.m2_classes set created_by = teacher_email;
alter table public.m2_classes alter column teacher_email drop not null;
alter table public.m2_classes add column lessons text[] not null default '{}';
alter table public.m2_classes add column ai_enabled boolean not null default false;
alter table public.m2_classes add column ai_daily_checks integer not null default 150 check (ai_daily_checks between 0 and 10000);
drop index public.m2_classes_teacher_name;
create unique index m2_classes_name on public.m2_classes (lower(name));

-- A student may be in several classes: the key is (class, email).
alter table public.m2_class_members drop constraint m2_class_members_pkey;
alter table public.m2_class_members add primary key (class_id, email);
create index m2_class_members_email on public.m2_class_members (email);

-- A class's teacher is never also one of its students, whichever side is changed.
create function public.m2_teacher_is_not_student() returns trigger language plpgsql as $$
begin
  if tg_table_name = 'm2_class_members' then
    if exists (select 1 from public.m2_classes where id = new.class_id and teacher_email = new.email) then
      raise exception 'teacher_is_student' using errcode = '23514';
    end if;
  else
    if new.teacher_email is not null and exists (select 1 from public.m2_class_members where class_id = new.id and email = new.teacher_email) then
      raise exception 'teacher_is_student' using errcode = '23514';
    end if;
  end if;
  return new;
end $$;
create trigger m2_members_teacher_check before insert or update on public.m2_class_members
  for each row execute function public.m2_teacher_is_not_student();
create trigger m2_classes_teacher_check before insert or update of teacher_email on public.m2_classes
  for each row execute function public.m2_teacher_is_not_student();

-- Taking a role away. For 'admin' it counts the other admins and deletes in one step, so two admins removing each other at the
-- same moment cannot leave none. p_settings_admins is how many admins the app's settings name (they stay admins regardless).
-- Returns 'removed', 'absent' or 'last_admin' (nothing deleted).
create function public.m2_take_role(p_email text, p_role text, p_settings_admins integer default 0) returns text
language plpgsql as $$
declare others integer;
begin
  perform pg_advisory_xact_lock(hashtext('m2_roles_admin'));
  if not exists (select 1 from public.m2_roles where email = p_email and role = p_role) then
    return 'absent';
  end if;
  if p_role = 'admin' then
    select count(*) into others from public.m2_roles where role = 'admin' and email <> p_email;
    if others + coalesce(p_settings_admins, 0) = 0 then
      return 'last_admin';
    end if;
  end if;
  delete from public.m2_roles where email = p_email and role = p_role;
  return 'removed';
end $$;

alter table public.m2_roles enable row level security;
revoke all on public.m2_roles from public, anon, authenticated;
grant all on public.m2_roles to service_role;
revoke all on function public.m2_take_role(text, text, integer) from public, anon, authenticated;
grant execute on function public.m2_take_role(text, text, integer) to service_role;
commit;
