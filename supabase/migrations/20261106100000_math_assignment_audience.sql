-- Focus practice (app/assignments.py): an assignment given to chosen students of the class instead of all of it.
-- Additive: existing assignments keep an empty audience, which means the whole class.
begin;
alter table public.math_assignments
  add column student_emails text[] check (student_emails is null or cardinality(student_emails) between 1 and 200);
comment on column public.math_assignments.student_emails is 'null: the whole class; else only these students (emails)';
commit;
