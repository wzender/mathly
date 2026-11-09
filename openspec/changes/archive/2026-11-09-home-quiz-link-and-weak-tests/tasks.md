# Tasks

## 1. The data

- [x] 1.1 Drop the skills fields from the behind lessons in `GET /api/home` and add the weak practice tests (test, number, best grade, the test's date and days left, whether an attempt is open) for the upcoming tests, earliest test first; verify API tests for every scenario of "Lessons behind on home" and "Practice tests below the pass line", and that home still needs no more waits in a row than before

## 2. The screen

- [x] 2.1 Shorten the behind card to the name, the date and the בוחן link with the best grade, and add the card of practice tests below 87 with a link to retake each; verify Playwright tests: no skills link on the behind card, the weak practice test shows with its grade and its link opens the exam, a test not taken or at 87 is not listed, no card when none, no sideways scrolling at 360px

## 3. Wrap-up

- [x] 3.1 Update the PRD (STU-1); run the full suite and `openspec validate home-quiz-link-and-weak-tests --strict`; verify both pass
