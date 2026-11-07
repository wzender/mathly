-- The prompter's outlines (ראשי פרקים, app/prompter.py): short topic reminders per slide that Claude writes from a
-- saved text, kept with it. Additive: one nullable column, and the AI usage log may now also say 'prompter'.
-- Rollback: alter table public.math_prompter_texts drop column outline; and restore the old feature check.
begin;
alter table public.math_prompter_texts
  add column outline text check (outline is null or char_length(outline) between 1 and 20000);
alter table public.math_ai_usage drop constraint math_ai_usage_feature_check;
alter table public.math_ai_usage add constraint math_ai_usage_feature_check
  check (feature in ('photo', 'grading', 'prompter'));
commit;
