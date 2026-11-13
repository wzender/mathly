-- Mathly 2: the developer's prompter (change add-prompter, PRD DEV-2). Additive, safe to run again.
-- Each developer's saved texts, on every device: a title (1-120), the text (up to 100,000 characters) and, once asked for, the AI's
-- outline (ראשי פרקים, up to 20,000). Read and written only by the server with the secret key, like every m2_ table.
-- Also widens the AI usage records' kinds: the outline ("prompter") and a worksheet's draft ("worksheet", recorded since
-- add-subjects-and-worksheets but refused by the old check, so those costs were not kept).
-- Rollback: drop table m2_prompter_texts; and put back check (feature in ('photo', 'check')) on m2_ai_usage.
begin;

create table if not exists public.m2_prompter_texts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  title text not null check (char_length(title) between 1 and 120),
  body text not null check (char_length(body) between 1 and 100000),
  outline text check (outline is null or char_length(outline) between 1 and 20000),
  updated_at timestamptz not null default now()
);
create index if not exists m2_prompter_texts_user on public.m2_prompter_texts (user_id, updated_at desc);

alter table public.m2_prompter_texts enable row level security;
revoke all on public.m2_prompter_texts from public, anon, authenticated;
grant select, insert, update, delete on public.m2_prompter_texts to service_role;

alter table public.m2_ai_usage drop constraint if exists m2_ai_usage_feature_check;
alter table public.m2_ai_usage add constraint m2_ai_usage_feature_check
  check (feature in ('photo', 'check', 'worksheet', 'prompter'));

commit;
