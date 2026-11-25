## Why

Starting from a low estimated grade discourages; a grade the student already holds and can lose motivates daily practice (loss aversion), while it must still meet the truth by the test.

## What Changes

- Home's estimated grade is a held grade: it starts 25 above the forecast, the daily mission keeps it, a day without it loses a quarter of the lead, and the lead shrinks to 0 over the last 14 days (on the test's day it is the forecast).
- Beside it: "✓ הציון נשמר" when today's mission is done, else tomorrow's grade without it.
- The teacher keeps seeing the forecast. No storage: it is computed from the answers per day since the test was set.

## Impact

`mathly2/forecast.py` (`held`, `mission_rounds`), `mathly2/realtests.py` (`_with_held` on the student's test card), `mathly2/static/home.js`, `mathly2/static/app.css`. No migration.
