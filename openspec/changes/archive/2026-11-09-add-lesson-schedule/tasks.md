# Tasks

## 1. The quiz

- [x] 1.1 Make the lesson quiz 15 questions in 20 minutes and add the pass mark (grade 87); verify unit tests: a quiz is drawn with 15 questions and at least three per skill for a four-skill lesson, 13 of 15 passes and 12 of 15 does not, a pass stays after a worse retake

## 2. The curriculum

- [x] 2.1 Add the migration and the store methods for the lesson dates (in memory and Supabase, remembered briefly by the cache wrapper and forgotten on change), and `GET /api/curriculum` and `PUT /api/curriculum` for managers and developers (in the permissions matrix); verify API tests: a manager sets, changes and clears a date, a teacher and a student are refused, an unknown lesson is refused, a bad date is refused, and the migration applies on a real PostgreSQL
- [x] 2.2 Add the "תכנית לימודים" tab to the manager screen; verify a browser test: dates are entered, saved and shown again, and the tab fits a phone without sideways scrolling

## 3. The path

- [x] 3.1 Give each lesson of `/api/path` its date, whether it is completed (all skills mastered or quiz passed) and whether it is behind, and the count of lessons behind; verify API tests for every scenario of "A completed lesson" and "Lessons behind the curriculum"
- [x] 3.2 Show "הושלם" and the behind marker with its date on the lesson hub, and the count at the top of the path; verify browser tests: a behind lesson, a completed lesson and a lesson with no date look right at 360px, nothing is locked, the marker is in words and not by colour alone

## 4. Wrap-up

- [x] 4.1 Update the PRD (QZ-1, QZ-2, QZ-3, the path and the manager's screens); run the full suite and `openspec validate add-lesson-schedule --strict`; verify both pass
