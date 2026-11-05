-- A quiz hand-in's 4-digit code (app/answer_routes.py): the same number on every request of one sitting, shown to the
-- student and on the teacher's AI queue, so the two can talk about the same hand-in. Additive; empty for other requests.
begin;
alter table public.math_ai_requests add column code text not null default '' check (code ~ '^[0-9]{0,4}$');
commit;
