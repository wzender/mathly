# Proposal

## Why

A teacher (and the developer) sees what each student has mastered, but not how much or how long they practise, overall and day by day.

## What Changes

- A "פעילות" view in the progress tab: for each student, the exercises, the estimated time, the active days and the share right over the last 7, 14 or 30 days, the exercises and time since the school year began, the last active day, and the days as bars that open a day-by-day table.
- Time is estimated from the gaps between answers (up to 3 minutes each; a gap over 5 minutes is a break) and, for quizzes and tests, from start to hand-in.
- A view `m2_daily_practice` (one row per student and day) and a route `/api/classes/{id}/activity`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `class-progress-views`: each student's activity.

## Impact

- `progress.py` (`class_activity`), `store.py` (`daily_practice`; answers keep their time in memory too), migration `20261124090000_m2_daily_practice.sql`; `static/teacher_progress.js`. PRD.
