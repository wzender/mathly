## Why

The teacher should see what the students ask the AI tutor on practice questions, as with photographed questions.

## What Changes

- The conversations are kept in a new table `m2_tutor_chats` (a row a student, question and day); the daily limit is counted there.
- The teacher's AI tab lists them ("שיחות עם ה־AI בתרגול"), by student and period, with the skill, the question and whether the student asked before answering.
- The student's chat says the teacher sees it.
- Before the migration is run, the chat still works and nothing is kept; the teacher is told to run it.

## Impact

Migration `20261127090000_m2_tutor_chats.sql`; `mathly2/store.py`, `mathly2/practice_tutor.py` (`GET /api/teaching/tutor-chats`), `mathly2/static/teacher_tutor.js`, `mathly2/static/teacher_ai.js`, `mathly2/static/exercise.js`.
