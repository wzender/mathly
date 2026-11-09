# Tasks

## 1. The quiz time

- [x] 1.1 Make a lesson quiz 3 minutes per question (45 for 15) in the code, the test fixtures and the screens that name it; verify the quiz timer starts at 45:00 and an attempt is due 45 minutes after it starts

## 2. The list

- [x] 2.1 Add the migration (`m2_review` with one row per student and question, `m2_review_done` for the daily goal) and the store methods (in memory and Supabase), with `daily_correct` adding the review answers; verify unit tests, the migration on a real PostgreSQL, and that a review answer does not move a practice round
- [x] 2.2 Add wrong answers to the list where a practice answer is graded and where a quiz, an exercise test or the simulation is submitted or settled (unanswered counts); verify API tests for every scenario of "Wrong answers go to חזרה"
- [x] 2.3 Add `GET /api/review` and `POST /api/review/answer` (the right choice never sent before the answer, none shown after a wrong one, a right answer removes the question, mastery and rounds untouched, the daily goal up by one) and the permissions matrix; verify API tests for "The חזרה tab", "Redoing a question" and "Practice only"

## 3. The screen

- [x] 3.1 Add the "חזרה" tab to the student's bar and the `review.js` screen (count, one question, the mistake and its tip after a wrong answer, empty state); verify Playwright tests: the tab fits a phone, a wrong practice answer appears there, a right answer removes it, a wrong one keeps it with the mistake and no right choice shown, empty state

## 4. Wrap-up

- [x] 4.1 Update the PRD (QZ-2, the new tab); run the full suite and `openspec validate add-review-tab --strict`; verify both pass
