# Proposal

## Why

The PRD (`docs/tasks/prd-mathly.md`) now describes the whole app with five roles, classes created by a manager, and mathly1's look. The foundation built so far has two roles and teacher-created classes, so every later stage would build on the wrong base. This stage puts the base right: who signs in, what each role may do, how classes are made, and the rules every screen follows.

## What Changes

- **BREAKING** Five roles: student, teacher, manager, admin, developer (PRD 4.1). Roles belong to an email; an admin gives and takes them; developers come only from the settings.
- **BREAKING** Classes are created, edited and deleted by a **manager** (PRD 4.2, 4.18), not by teachers. A class has lessons, one teacher, students, an AI switch (off) and a daily AI budget.
- **BREAKING** A student may belong to **more than one class**. A class's teacher can add and remove its students (TCH-9).
- The sign-in page and each role's home shell follow mathly1 (ACC-1, TCH-1, MGR-1, ADM-1). The sky look, always dark, becomes the rule for every screen.
- The exercise bank's rules are corrected: no worked or faded examples; content gaps are listed, not required before use.
- mathly1's database stays untouched, so the Hugging Face Space can be switched back (PRD 7.3, Fallback).

Screens: static mockup at `docs/mockups/mathly2-screens.html` (student, teacher, manager); this stage's screenshots are in [design.md](./design.md#screens-in-this-stage) and [screenshots/](./screenshots/).

## Capabilities

### New Capabilities

### Modified Capabilities
- `accounts-and-classes`: five roles, admin-given roles, manager-made classes, students in several classes, the teacher's roster.
- `app-basics`: the sky look, readability without color or motion, server-side time and decisions, the mathly1 fallback, safe settings.
- `exercise-bank`: the content rules match the PRD (mistakes, figures, start-up checks, no answers on the device, listed content gaps).

## Impact

- `mathly2/auth.py`, `mathly2/classes.py`, `mathly2/store.py`, `mathly2/config.py`, `mathly2/main.py`, the role screens in `mathly2/static/`.
- A new migration adds a roles table and the new class columns, and lets a student be in several classes (`m2_` tables only).
- New settings: `DEVELOPER_EMAILS`, `ADMIN_EMAILS` (the first admins).
- Later stages (`add-learning-core` onwards) build on these roles and classes.
