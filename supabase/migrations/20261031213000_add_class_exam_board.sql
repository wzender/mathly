alter table public.classes
  add column if not exists exams jsonb not null default '[]'::jsonb,
  add column if not exists exam_title text not null default '',
  add column if not exists exam_note text not null default '';

alter table public.classes drop constraint if exists classes_exams_are_array;
alter table public.classes
  add constraint classes_exams_are_array check (jsonb_typeof(exams) = 'array');
