## Why

Home should lead with what to do now: the current lesson, quick practice and a photographed question as big buttons; a way to close every gap at once; and the coming test's estimated grade and days left in plain sight, honest yet encouraging, with more (positive) pressure as the test nears.

## What Changes

- "תרגול בנסיעה" is renamed "תרגול מהיר".
- Big buttons under the status line: the current lesson, closing the gaps (when lessons are behind), quick practice and a photographed question. The next-step card is gone.
- Closing the gaps: one round of 5 questions on each lesson behind; a lesson above 90% has its skills marked mastered and is no longer behind (new attempt kind `gaps_round`).
- The test block shows the days left and the estimated grade big, with where the best 3 rounds take it; no number before 15 answers; a rise is shown, a dip is not; the mission and colours grow with the days left.

## Impact

Migration `20261128090000_m2_gaps_round.sql`; `mathly2/rounds.py` (`POST /api/gaps/start`), `mathly2/forecast.py` (`boost`), `mathly2/realtests.py`, `mathly2/static/home.js`, `mathly2/static/round.js`, `mathly2/static/student.js`, `mathly2/static/app.css`.
