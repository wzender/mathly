# Tasks

## 1. Server

- [x] 1.1 Read the version from `mathly2/version.json`, else git, else nothing; verify tests: the file wins, a broken or missing file falls back
- [x] 1.2 Add `GET /api/dev/status` (developers only) with the overall state, version, start time, uptime and one check per part; the database check bypasses the cache; verify tests: 401/403/200, states without Supabase, a set key is ok and never returned, a failing database is an error

## 2. Screen and deploy

- [x] 2.1 Show the card first on the developer's home, with dates in Israel's time and a refresh button; verify Playwright tests on a phone and a desktop: the version, the update date, every row, no sideways scroll
- [x] 2.2 Write `mathly2/version.json` in the Hugging Face sync before pushing; dry-run the step on a scratch clone

## 3. Wrap-up

- [x] 3.1 Update the PRD (DEV-5) and run the full suite
