# Tasks

## 1. Data

- [x] 1.1 Add the view `m2_activity` and an index on `m2_answers.day`, server only; verify on a local PostgreSQL: one row per person and day, an attempt at 00:30 Israel time counts on that day, the browser roles are refused
- [x] 1.2 Read it in both stores (`activity_since`), in pages on Supabase; verify tests: the in-memory store matches the view, the Supabase store pages through

## 2. Route and screen

- [x] 2.1 Add `GET /api/dev/activity` (7 or 30 days, developers only, counts only); verify tests: per-day counts with empty days, a person once a day, the range total, 401/403/422
- [x] 2.2 Draw the chart, tiles, tooltip and table on the developer's home with a 7/30 toggle; verify Playwright tests on a phone and a desktop

## 3. Wrap-up

- [x] 3.1 Update the PRD (DEV-6) and run the full suite
