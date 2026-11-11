# Proposal

## Why

A developer cannot see how much the app is used: how many people were active today, and day by day over the last week.

## What Changes

- **An activity card on the developer's home**, below the status card: a column chart of how many different people were active on each of the last 7 days (or 30), with today's count, the range's total of different people, practice answers and started quizzes and tests, a tooltip per day and a table.
- **A view `m2_activity`** (migration `20261116090000_m2_activity.sql`): one row per person and Israel day, from practice answers and started attempts. Server only.
- `GET /api/dev/activity?days=7|30`, developers only, returns counts, never who.

## Capabilities

### Modified Capabilities
- `system-status`: "Activity chart" is added (PRD DEV-6).

## Impact

- New migration (a view and an index on `m2_answers.day`); until it is applied on Supabase, the activity card shows an error and the rest of the developer's home works. `status.py`, `store.py` (both stores), `developer.js` and its styles, tests, PRD DEV-6.
