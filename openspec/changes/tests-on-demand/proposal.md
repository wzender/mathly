# Proposal

## Why

A student two days before a real test was blocked. The plan of two numbered exercise tests and one simulation opened on certain days and could be taken once. The readiness number mixed in mastery of the path, so the student could not tell which action would raise it. On the home screen it was not clear that tapping the test strip leads to the tests.

The readiness number should be the one thing the app pushes the student to raise, and the student should always have a test to take.

## What Changes

- **Tests on request.** The student asks for:
  - a **simulation**: all the test's material, its length and time, no choice, as many as they like (an open one resumes);
  - a **practice test** in one of three modes:
    - *balanced*: all the material evenly;
    - *focused*: 15 questions from the skills that lost points in this test's tests, or are still being learned;
    - *manual*: the skills the student picks.
  
  There are no windows, no one-time rule and no "start the skills first" refusal. Every test draws from the whole material, unstarted skills included.
- **Readiness moves only with tests, never with the path or deepening.** Each handed-in test pulls the number toward its grade, and only up:

  `number += GAIN × (grade − number)` when the grade is above the number.

  GAIN is 0.6 for a simulation, 0.3 for a practice test and 0.15 for a manual one (picked skills can skip the hard ones). Levels: מתחילים, בדרך (40), כמעט שם (70), מוכנים (85).
- **Making the number feel like a game:**
  - The home block and the test page show the level and the points to the next level.
  - The number counts up from the last visit with a "+N" badge.
  - Each button shows the most it can add now ("+30", "+60").
  - A result opens with the gain (big "+N", the bar growing, "🎉 רמה חדשה"), and buttons for another simulation or practice test.
  - The test page lists every test handed in with what it added.
- **Home:** one compact block with the number, the level and the days left (a link to the test's page), a thin bar, and two buttons, **📝 מבחן תרגול** and **⏱ מבחן סימולציה**. The countdown plan, today's task, the "required simulation" chip and the weak practice tests list are gone. The home still fits one screen.
- **Teacher:** the tests tab and the progress tab show readiness, how many practice tests and simulations were taken, and the best grade of each. Mastery is shown beside readiness, not inside it.

## Capabilities

### Modified Capabilities
- `real-tests`: on-demand practice tests (3 modes) and simulations; readiness from tests only.
- `student-home`: the test block with two buttons.

## Impact

- `readiness.py` (rewritten), `realtests.py` (facts, card, starting tests; new `POST /api/tests/{id}/practice/start`), `exam.py` (modes), `quizzes.py` (a result's `readiness` change; grades by mode), `progress.py`, `boardwork.py` (titles).
- `countdown.py` and its tests are removed.
- Frontend: `home.js`, `testcard.js`, `quiz.js`, `student.js` (`#/test/<id>/practice`), `teacher.js`, `teacher_progress.js`, `grades.js`, `app.css`.
- No database change. Old attempts keep counting: exercise tests 1 and 2 are balanced practice tests, 3 is focused.
