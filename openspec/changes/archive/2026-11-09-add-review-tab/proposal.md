# Proposal

## Why

A wrong answer is final where it happens (path practice, a quiz, a test), and the student never sees it again, so what they got wrong is forgotten. And 20 minutes for a 15-question quiz is too tight.

## What Changes

- **A new student tab "חזרה"**: every question the student got wrong goes there, from path practice, the lesson בוחן, the practice tests and the simulation. A question left unanswered when a בוחן or a test is submitted also counts as wrong.
- **In חזרה the student redoes the question**, one at a time, and a right answer removes it. A wrong answer keeps it there and names the mistake and its tip, without showing the right choice.
- **Redoing a question in חזרה is practice only**: it does not change skill mastery, grades or the readiness meter. Each right answer counts toward the daily goal.
- **The lesson בוחן gets 3 minutes per question**: 45 minutes for its 15 questions (it was 20).

## Capabilities

### New Capabilities
- `review`: the wrong-answer list, redoing it, and what it does and does not change.

### Modified Capabilities
- `lesson-quizzes`: the quiz time.

## Impact

- A migration (`m2_review`, `m2_review_done`), store methods, `GET /api/review` and `POST /api/review/answer`, hooks where a wrong answer is graded (practice) and where a quiz or test is submitted or settled, the daily goal (`daily_correct` adds the review answers), a sixth tab on the student's bar and a `review.js` screen. PRD QZ-2 and a new section.
- Wrong answers given before this change are not added.
