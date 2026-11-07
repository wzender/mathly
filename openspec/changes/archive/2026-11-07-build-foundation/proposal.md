# Proposal

## Why

Mathly is being rebuilt from scratch (see `docs/tasks/prd-mathly.md`). Every later feature needs the same base first: a running app in Hebrew and right-to-left, sign-in, classes, and the exercise bank loaded and readable.

## What Changes

- New app in `mathly2/`, next to the current app, which keeps running until the new one replaces it.
- Same stack as today: Python FastAPI server, Supabase for sign-in and data, plain JavaScript front end.
- Google sign-in; teachers from a list in the settings; teachers create classes and add students by email.
- The exercise bank is copied into the new app, checked on start-up, and served to the front end, with math shown as formulas.
- A report of the content the bank still lacks (worked examples, faded examples, "why this step?" choices, lesson quizzes).
- A rule and a base for grades: only the server writes them.
- Starts empty: no data moves from the current app.

## Capabilities

### New Capabilities
- `app-basics`: Hebrew, right-to-left, phone first; grades kept on the server.
- `exercise-bank`: the bank as the source of lessons, skills, questions and mistakes; math shown as formulas; known content gaps.
- `accounts-and-classes`: Google sign-in, teacher accounts, classes and their students.

### Modified Capabilities

## Impact

- New folder `mathly2/` with its own server package, static files, tests, Supabase migrations and Dockerfile.
- New Supabase tables (prefix `m2_`) in the existing Supabase project, reusing its Google sign-in setup.
- The current app (`app/`, `static/`) is not changed.
