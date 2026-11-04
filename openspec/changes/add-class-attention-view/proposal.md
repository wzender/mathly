# Proposal

## Why

The class report ("הכיתה שלי") is a list of collapsed cards, one per student, ordered as the class roster. To find out who needs help, the teacher has to open every card and compare numbers in their head, and nothing in the report shows change over time. A teacher with 30 students needs to see in seconds who has stopped practising, who is stuck, and which skill the whole class is stuck on, and plan the next lesson from that.

## What Changes

- Add a **"needs attention" (דורשים תשומת לב)** section at the top of the report. It lists the students who match at least one signal, each with the reasons in plain words:
  - no practice for 7 days or more,
  - stuck on a skill: 3 or more wrong answers in it in the last 14 days without finishing it,
  - practice this week less than half of last week (with at least 10 correct answers last week),
  - latest unit-quiz grade below 55 (server grade, from `add-server-quiz-grades`),
  - signed in but never practised.
- Add a **students × skills grid** tab for a chosen unit: one row per student and one column per skill, each cell showing the star state (gold, finished, fading, practising, not started). A column summary counts how many students finished each skill, and practising-but-not-finished columns with many students are highlighted as class-wide difficulties.
- Add a **units overview** in the grid: one column per unit of the class, each cell showing finished skills out of the unit's skills.
- Show **weekly activity** on each student's card: correct answers this week and last week, from the per-day counts already saved.
- Let the teacher **sort** the student list by attention, name, progress or last activity.
- Show students by the class's **nickname** for them, then their Google name, then the part of the email before the @ (today it is always the email part).
- The report needs two more fields from each student's progress (`seen`, `tries`) and each student's Google name.

## Capabilities

### New Capabilities

- `class-report`: what the class teacher sees about their students: who needs attention and why, the students × skills grid, weekly activity, sorting and student names.

### Modified Capabilities

(none: there are no main specs yet)

## Impact

- `app/class_report.py`: `report_part` adds `seen` and `tries`; each student entry adds `name` (class nickname or Google full name).
- `app/auth.py`: `user_ids` (or a sibling) also returns each user's display name from the Supabase admin user list.
- `static/math.js` (class report section): attention computation, the grid tab, sort control, weekly activity, names.
- `static/math.css`: grid and attention styles, readable on a phone (the grid scrolls sideways inside its own box, never the page).
- `static/guide.js` teacher tab, `README.md` class-teacher section.
- Tests: `tests/test_class_report.py`, a new browser test for the report.
- Depends on `add-server-quiz-grades` for the low-grade signal. Without it, that signal is left out.
