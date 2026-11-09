# Tasks

## 1. The data

- [x] 1.1 Share the path's lesson facts with home and add the behind lessons to `GET /api/home` (name, date, mastered and total skills, the next unmastered skill, the בוחן's best grade and whether one is open), earliest date first; verify API tests for every scenario of "Lessons behind on home", and a timing test that home needs no more waits in a row than before

## 2. The screen

- [x] 2.1 Show the card "שיעורים בפיגור" on home with the two options per lesson; verify Playwright tests: the card lists the lessons in date order with both options and the links open the next skill and the בוחן, the best grade and "13 מתוך 15" show, no card when none is behind, no sideways scrolling at 360px

## 3. Wrap-up

- [x] 3.1 Update the PRD (STU-1); run the full suite and `openspec validate add-behind-lessons-to-home --strict`; verify both pass
