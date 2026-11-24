## Why

A photographed question with sub-parts (א, ב, ג) was read with its first part only, so the student practised a third of the question.

## What Changes

- The AI reads the givens and every sub-part, each part on its own line; when the photo holds several questions it reads the complete one in the middle.
- The answer is kept as a line a part ("א. $∠B = 30°$"); a final-answer box for each part whose answer is a plain number, labelled with its letter. A wider plain-answer pattern ("∠B = 30°", "BP = 12 ס\"מ").
- One board and one grade for the whole question (equal weight a part); the check adds a verdict and a sentence of feedback a part.
- The teacher edits the multi-line answer in a text area and sees the per-part feedback.

## Impact

`mathly2/photoq.py`, `mathly2/boardreview.py`, `mathly2/static/photoq.js`, `mathly2/static/teacher_photoq.js`, `mathly2/static/app.css`. No migration.
