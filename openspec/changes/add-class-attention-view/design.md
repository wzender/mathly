# Design

## Context

- `GET /api/classes/{id}/report` (`app/class_report.py`) returns, per student, a slice of the saved progress object (`report_part`: `done, gold, days, missed, slips, quizzes, uq, updated`). The page computes everything else with the same functions the student's own page uses (`reportOf` in `static/math.js`, `MathlySky.patterns`, `MathlySky.star`).
- `P.days` maps `YYYY-MM-DD` to correct answers that day. `P.slips` is a log of wrong answers with skill, question, misconception and time. `P.seen[id]` is the last time a skill was practised, and the fading rule (`MathlySky.fading`) uses it.
- Classes already store `nicknames` (email → name) set in the class editor (`app/auth.py`).

## Goals / Non-Goals

**Goals:**
- All signals and grid states computed in the browser from the data the report already loads, plus `seen`, `tries` and a name, with no new table.
- Use the student's own rules (fading, patterns) so the teacher and the student see the same state.

**Non-Goals:**
- A server-side event log or long-term trends beyond two weeks (a later change can add one).
- Alerts or push notifications to the teacher.
- Teacher-configurable thresholds. They are constants for now, see below.

## Decisions

**Compute attention in the page, not on the server.** The report page already runs the patterns logic, and the signals are small functions over the same object. Keeping them next to `reportOf` avoids duplicating the rules in Python. Alternative considered: a server endpoint `GET /report/attention`. Rejected because it would duplicate `fading`/`patterns` logic in two languages.

**Constants, in one place in `math.js`:** `INACTIVE_DAYS = 7`, `STUCK_SLIPS = 3` within `STUCK_WINDOW_DAYS = 14`, `DROP_RATIO = 0.5` with `DROP_MIN_LAST_WEEK = 10`, `LOW_GRADE = 55`, `CLASS_DIFFICULTY_SHARE = 1/3`. Weeks are Sunday–Saturday (the Israeli school week), using the device's local dates as `P.days` does.

**"Practising" state.** A skill is practising when `tries[id] > 0` (or it has slips) and `done[id]` is unset. That is why `report_part` adds `tries` and `seen`.

**Names.** `auth.user_ids` already pages through the Supabase admin user list. It will also return `user_metadata.full_name` (or `name`). The report puts `name` = class nickname, else full name, else null, and the page falls back to the email prefix.

**Grid layout.** A table with a sticky first column (names) inside a sideways-scrolling container. Cells are 28 px coloured squares with text alternatives (`aria-label`). On a phone the grid scrolls inside its box, never the page. The tab choice (list / grid), chosen unit and sort order are kept in `localStorage` under `mathly.report.*`, wrapped in try/catch.

**Low-grade signal.** It reads the server grades added by `add-server-quiz-grades`. If that change is not deployed (no `quiz_sittings` in the response), the signal is skipped instead of using device scores.

## Risks / Trade-offs

- [Signals use device-reported practice data] → Labelled as such (from `add-server-quiz-grades`). These are prompts for the teacher to look, not grades.
- [Clock and timezone differences between devices] → Day keys are already local dates. A one-day error at week boundaries is acceptable for these signals.
- [Large classes make the grid wide] → One unit at a time (10 skills) keeps it within about 400 px.
- [Admin user list paging cost for names] → Same call the report already makes; no extra request.
