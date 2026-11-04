-- Lesson resources a teacher chooses to show students (app/unit_resources.py). Additive: one column. Every resource
-- added before this starts hidden, so nothing a teacher photographed for themselves reaches a student by surprise.
begin;
alter table public.math_unit_resources add column visible boolean not null default false;
create index math_unit_resources_visible on public.math_unit_resources(unit_id, created_at desc) where visible;
commit;
