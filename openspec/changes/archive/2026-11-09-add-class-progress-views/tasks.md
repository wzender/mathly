# Tasks

## 1. The data

- [x] 1.1 Add store reads that fetch the progress rows and the attempts of many students in one call (in memory and Supabase); verify unit tests: rows of several students come back together, an empty list gives nothing, other students are not mixed in
- [x] 1.2 Add `GET /api/classes/{id}/progress?period=1|2` returning the students, the lessons of the period with their skills and dates, each student's skill states as of the period's end, the coverage (percent, best quiz grade, completed, behind) and the readiness for the nearest coming test; add the number of students to `GET /api/teaching/counts`; verify API tests for every scenario of the progress by lesson, periods and readiness, the permissions (own teacher, other teacher, developer, manager, admin, student) and the permissions matrix; verify a timing test: a class of 25 students needs no more waits in a row than a class of 2

## 2. The screens

- [x] 2.1 Add the "התקדמות" tab (with its number) and the card shortcut, the class picker, the period tabs and the two views (progress by lesson, readiness); verify Playwright tests: each cell shows its state in a symbol and a word, no column stands for a skill, the table scrolls inside its frame and the page does not scroll sideways at 360px and 1280px, a student who never signed in is all not started,, the picker switches classes, the period tabs change the lessons shown

## 3. Wrap-up

- [x] 3.1 Update the PRD (TCH-1, TCH-7, TCH-8); run the full suite and `openspec validate add-class-progress-views --strict`; verify both pass
