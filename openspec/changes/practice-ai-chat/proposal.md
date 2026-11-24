## Why

The AI tutor chat helped on photographed questions; a student stuck on a regular practice question had only the static explanation.

## What Changes

- "💬" on the exercise screen opens a chat with the AI tutor about the question on screen (practice only, not quizzes, the simulation or test rounds).
- Before answering it guides without revealing the right choice, and that answer does not count for mastery; after answering it explains the answer and the mistake.
- The conversation stays in the browser with its question; while open, a right answer waits for the button instead of the countdown. 30 messages a day a student.

## Impact

New `mathly2/practice_tutor.py` (`POST /api/skills/{skill_id}/tutor`), `mathly2/skills.py` (`tutor` flag), `mathly2/boardreview.py` (a context note), `mathly2/static/exercise.js`, `mathly2/static/app.css`. No migration.
