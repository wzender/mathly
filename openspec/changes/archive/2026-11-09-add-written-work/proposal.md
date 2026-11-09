# Proposal

## Why

Teachers need to give work from the material they already have and check it, and students need to hand in full written solutions (PRD 4.14, TCH-2 – TCH-4, STU-5). Written answers are also what the AI checks in stage 7.

## What Changes

- A written answer is handed in as a picture: from the board, from the phone's camera, or, on a computer, by uploading or asking the student's own phone (a 4-digit code) with a push notification.
- Answer pictures are kept privately until 31 August of the school year.
- Teachers create assignments from a file, a photo, the board, or one of the bank's written quizzes, for a class; or send one of a real test's exercise tests as an assignment (EXT-2).
- Students see "המשימות שלי" on home, hand in, and see the grade and note or a request to correct.
- One teacher inbox of everything waiting, oldest first; grading 0–100 with a note, or sending back.

Screens: `docs/mockups/mathly2-screens.html` (student tab: home assignments; teacher tab: inbox).

## Capabilities

### New Capabilities
- `written-answers`: handing in pictures, the phone photo request and push notifications, and where pictures are kept (PRD ANS-1 – ANS-3, PSH-1, PSH-2).
- `assignments`: giving, handing in, the inbox and grading (PRD TCH-2 – TCH-4, STU-5, QZ-6).

### Modified Capabilities

## Impact

- Builds on `smart-board` (hand-in), `accounts-and-classes` and `grades`.
- New `m2_` tables for assignments, submissions, answer pictures and push subscriptions; a private storage bucket for pictures (not mathly1's).
- New settings for the push keys and the picture bucket. Ports mathly1's `static/answer-scans.js` behavior and service worker.
