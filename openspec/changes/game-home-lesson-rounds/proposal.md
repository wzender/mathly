# Proposal

## Why

A parent installed the app for their child: the skills-and-lessons structure is too heavy. A lesson is about 50 exercises (5 skills × a round of 10), which discourages, and the home is a column of cards that does not show at a glance what is done and what is left. The goal is that the child masters the skills; the home should show, simply and like a game, which lessons are done and which are still waiting, and make them want to play the next one. The path stays, for going deeper.

## What Changes

- **A lesson round (סבב שיעור):** 10 questions from the lesson's skills, with instant feedback like the exercise screen (a celebration, the mistake's tip). It draws only from skills not mastered yet, at most 3 per skill, so it gets shorter as the lesson fills up (a lesson with one skill left is a round of 3). A lesson whose skills are all mastered draws 10 from all of them. Its answers are practice answers: they count for mastery, the daily goal and the review list.
- **Stars per lesson:** ⭐ a round finished, ⭐⭐ a round with 8 or more right of 10 (80%), ⭐⭐⭐ every skill of the lesson mastered ("מושלם"). Because mastery needs two days, the third star means coming back another day; a round's result says which skills are one good day away.
- **The home is one screen**, like a game's level select: the stars collected, the lessons perfected, the streak and the daily goal; one big "play" button for the next lesson; the nearest test in one strip (days left, readiness number, today's task); small buttons for a required simulation, the new assignments and photo help; and every lesson as a small tile with its number (a crown when perfect), its stars, "⏰" when behind and "◐" when a round is open. Tapping a tile opens its round. It fits 360×800 with all 24 lessons. The readiness bar and the practice tests to retake move to the test's card; the behind card is replaced by the mark on the tile; the assignments list becomes one button to "הגשות".
- **The path is for going deeper:** its tab is named "העמקה"; nothing else changes on it.

## Capabilities

### New Capabilities
- `lesson-rounds`: the lesson round and the lesson's stars.

### Modified Capabilities
- `student-home`: "Home shows only what is critical", "Continue the path", "Today's task", "Lessons behind on home" and "Practice tests below the pass line" (replaced by the one-screen board).
- `learning-path`: the tab's name.

## Impact

- New `mathly2/rounds.py` (start, read, answer), `mathly2/static/round.js`; `mathly2/skills.py` (`lesson_rows` gives stars and the round facts), `mathly2/realtests.py` (`/api/home` gives the map), `mathly2/static/home.js`, `student.js`, `ui.js`, `app.css`.
- Database: one widened check on `m2_attempts.kind` (adds `lesson_round`), migration `20261118090000_m2_lesson_rounds.sql`. It must be applied before deploying.
