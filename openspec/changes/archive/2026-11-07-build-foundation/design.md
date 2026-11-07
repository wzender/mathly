# Design

## Context

The current app (`app/`, `static/`) is FastAPI plus Supabase, called through Supabase's REST API. It already has Google sign-in, a teacher list from the `TEACHER_EMAILS` setting, and a Dockerfile for Hugging Face Spaces. Two parts are kept as they are (PRD 7.1): the exercise bank `app/math_algebra9.json` (24 lessons, 96 skills, 1,050 questions inside the skills, 244 mistakes) and the drawing board (`static/math-board.js`, `static/board-math.js`, `static/vendor/mathlive/`).

The bank writes math as plain text between `$…$` with Unicode signs (`$x² − 2x − 15$`), not as LaTeX. The current `static/math-tex.js` turns that text into TeX and draws it with MathJax.

## Goals / Non-Goals

**Goals:**
- A base that every later slice (`build-skill-learning`, `build-lesson-quizzes`, `build-assignments`, `build-test-prep`, `build-class-progress-views`) builds on without reworking it.
- Both apps can run side by side until the switch.

**Non-Goals:**
- Any learning, quiz, test or assignment screen. Those come in later slices.
- Writing the missing content. This change only reports what is missing.
- Changing or retiring the current app.

## Decisions

### Layout: one Python package in `mathly2/`
```
mathly2/
  __init__.py  main.py       # FastAPI app: uvicorn mathly2.main:app
  config.py                  # settings from environment
  clock.py                   # server time and Israel calendar day
  store.py                   # Supabase REST calls; InMemoryStore for tests
  auth.py  classes.py  bank.py
  content/math_algebra9.json # the bank (copied)
  static/                    # index.html, app.js, app.css, math-tex.js, MathJax setup
  supabase/migrations/
  tests/
  Dockerfile  README.md
```
The package is named `mathly2` so it never clashes with the current `app` package when both run from the repo root. *Alternative:* a separate repo, which the user ruled out.

### Copy the bank, then the new copy is the source
`mathly2/content/math_algebra9.json` is copied once. New content (worked examples, quizzes) goes only into the new copy. *Alternative:* sharing one file, which would let new fields break the current app.

### Supabase: same project, `m2_` tables, server-only writes
New tables live in the existing project with an `m2_` prefix, so Google sign-in keeps working with no new OAuth setup. Every `m2_` table has row-level security turned on and no policy for the anon or authenticated roles, so only the server (secret key) can read or write them. The browser uses Supabase only to sign in and send its token. This is how the "grades kept on the server" rule is enforced. *Alternative:* a new Supabase project. It's cleaner, but it needs a second Google OAuth setup, and that isn't needed to start empty.

Foundation tables:
- `m2_classes(id, name, teacher_email, created_at)`
- `m2_class_members(class_id, email unique, user_id null, added_at)`: one class per student, enforced by the unique email. `user_id` is filled on the student's first sign-in.

### Teachers from `TEACHER_EMAILS`
The same setting as today. It is simple, and there is no admin role (PRD open question 3 was answered: the teacher creates classes and adds students).

### Server clock and calendar day
`clock.py` gives the server's current time and the calendar day in `Asia/Jerusalem`. Every later rule that depends on days (mastery's "2 different days", the countdown, the simulation window) uses it, never the device's time.

### Front end: plain ES modules, no build step
One `index.html` with `dir="rtl"` and `lang="he"`, ES modules, and CSS tokens for light and dark mode. It is designed for phone width first (360–430px), with wider layouts added for the teacher screens later. The board files (later slice) and `math-tex.js` are plain scripts, so a build step would add nothing.

### Math shown with the current `math-tex.js`
The current `math-tex.js` and its MathJax setup are copied, because the bank's math is plain text, not LaTeX. The `exercise-bank` spec's "LaTeX inside `$…$`" is met by drawing every `$…$` as a formula. Whatever can't be read stays as text.

### Bank checked on start-up
`bank.py` loads the bank once and checks it: ids are unique, every question has one correct choice, every wrong choice's `mistake` exists, every mistake's `back` skill exists when it is filled in (204 of the 244 mistakes have it empty today; the content-gaps report lists them), and every skill's lesson exists. A broken bank stops the server from starting, with a clear message. The API serves lessons and skills, and questions only through later endpoints that hide which choice is correct.

### Local development without Supabase
When `SUPABASE_URL` is empty, the server uses `InMemoryStore` and a sign-in screen that takes an email (marked "dev only"). Tests use the same path. *Alternative:* requiring a Supabase project for development, which would slow down every test.

## Risks / Trade-offs

- [Two copies of the bank diverge] → Intended. The current app is retired at the switch.
- [Supabase REST without a client library] → Same approach as the current app. All calls go through `store.py`, so it can be swapped out in one place.
- [Teacher list in a setting] → Changing teachers needs a restart. That's fine at one school's scale.
- [Students stay in one class] → Matches the PRD. Moving a student means removing them and adding them again.

## Migration Plan

- Deploy `mathly2` as its own Hugging Face Space from `mathly2/Dockerfile`, with the same Supabase settings.
- Run the `m2_` migrations. They don't touch the current app's tables.
- Rollback: stop the new Space and drop the `m2_` tables.
