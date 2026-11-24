# Proposal

## Why

Students meet questions outside the app (worksheets, books, past exams) and want to practise them with the same board and feedback. Their
questions are also a source of new practice for the class.

## What Changes

- A student photographs a question with the phone (the 4-digit code) or from this device. The AI reads it at once (at most 5 a day), keeps its answer for the check, and suggests its skill or "external"; the student may change it.
- The question is answered like any question: on the board, with a box for a plain-number answer. The AI grades it 0-100 with a verdict and feedback on the way; then the full solution shows. At most 3 hand-ins a question.
- After its first check it waits for the class's teacher, who may fix it and approves it into the class's bank or rejects it. The class's other students solve approved questions from the same sheet.
- A photo request can now be for a question (no assignment).

## Capabilities

### New Capabilities

### Modified Capabilities
- `ai-help`: photographed questions.

## Impact

- `photoq.py` (new), `boardreview.py` (reading and open grading with Gemini), `written.py` (photo requests for a question, picture access), `boardwork.py` (boards for `pq:` refs), `push.py`, `store.py`, `realtests.home` (`photoq`); `static/photoq.js`, `static/teacher_photoq.js` (new), `static/phone.js`, `static/student.js`, `static/home.js`, `static/teacher_ai.js`. Migration `20261125090000_m2_photo_questions.sql`. PRD STU-1.
