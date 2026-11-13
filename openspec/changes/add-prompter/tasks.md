# Tasks

## 1. Data

- [x] 1.1 Add the migration `20261119090000_m2_prompter.sql`: `m2_prompter_texts` with server-only grants, and widen the AI usage kinds to `prompter` and `worksheet`. Verify with the migration tests on a local PostgreSQL.
- [x] 1.2 Add the prompter store methods to `InMemoryStore` and `SupabaseStore`, and refuse an unknown AI usage kind. Verify with the API tests.

## 2. Server

- [x] 2.1 Add `ai.outline` (ported from mathly1) to the Anthropic, missing and fake clients. Verify with the fake client in the API tests.
- [x] 2.2 Add the `/api/prompter` routes for developers: list, create, change, delete and outline, with the limits and Hebrew failures. Verify with `test_prompter_api.py` and the permission matrix.

## 3. Screen

- [x] 3.1 Port `static/prompter.js` from mathly1 and add the developer screen's card (`static/prompter_card.js`). Verify with `test_prompter_browser.py` on a phone and a desktop: save, the draft kept across a reload, the AI outline, the full-screen view, delete, and a failed outline.
- [x] 3.2 Update PRD DEV-2 and move the prompter out of `add-developer-tools`. Verify that `openspec validate add-prompter --strict` and `openspec validate add-developer-tools --strict` pass.

## Workflow follow-up

- Apply `20261119090000_m2_prompter.sql` in Supabase before deploying.
- Archive the change after review.
