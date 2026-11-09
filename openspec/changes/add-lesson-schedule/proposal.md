# Proposal

## Why

The course follows a curriculum: each lesson is meant to be finished by a certain date. Students cannot see whether they are on time, and finishing a lesson takes about 50 exercises (about 5 skills of 10 questions) with no quicker way to show that a student already knows it.

## What Changes

- **A date per lesson**, one school-wide curriculum set by a manager (or a developer) in a new "תכנית לימודים" tab of the manager screen. A lesson without a date is never behind.
- **The path marks every lesson that should be finished by now**: a lesson whose date has passed and that is not completed carries a marker and a sentence ("היה אמור להסתיים ב־3.11"), and the path says how many lessons are behind.
- **A lesson is completed in either of two ways**: every one of its skills is mastered, or its quiz was passed with at least 13 right out of 15. Passing the quiz does not change the skills' own mastery.
- **The lesson quiz becomes 15 questions** (from 10), in 20 minutes (from 15). Its grade is still right answers out of the questions, so 13 of 15 is a grade of 87; the pass is a best grade of at least 87.

## Capabilities

### New Capabilities
- `curriculum`: the date of each lesson and who sets it.

### Modified Capabilities
- `lesson-quizzes`: 15 questions in 20 minutes; the pass mark.
- `learning-path`: completed lessons and lessons behind the curriculum.

## Impact

- A migration (`m2_curriculum`), store methods, `GET/PUT /api/curriculum`, `quiz.py`/`attempts.py` (size, minutes, pass), `skills.py` (path), `manager.js`, `path.js`, the cache wrapper, the permissions matrix; PRD QZ-1..3, PTH, MGR.
- Quizzes already taken keep their grade (a 9 of 10 is 90, which passes): no quiz is re-graded.
