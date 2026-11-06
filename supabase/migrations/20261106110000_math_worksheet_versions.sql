-- Worksheet hand-ins with versions (app/worksheets.py): the teacher may return a submission for a fix, and the
-- student's new hand-in is the next version; the earlier ones stay to look back at. A hand-in also carries a note
-- to the teacher. Additive: existing submissions become version 1, "checked" when the teacher checked them.
begin;
alter table public.math_worksheet_submissions
  add column version integer not null default 1 check (version between 1 and 20),
  add column state text not null default 'submitted' check (state in ('submitted', 'checked', 'returned')),
  add column note text not null default '' check (char_length(note) <= 300),
  add column returned_at timestamptz,
  add column return_comment text not null default '' check (char_length(return_comment) <= 1000),
  add column return_due_on date;
update public.math_worksheet_submissions set state = 'checked' where checked_at is not null;
alter table public.math_worksheet_submissions drop constraint math_worksheet_submissions_worksheet_id_student_id_key;
alter table public.math_worksheet_submissions add constraint math_worksheet_submissions_version_key
  unique (worksheet_id, student_id, version);
commit;
