# Proposal

## Why

Multiple-choice answers show only the final answer. The teacher (and the parent) want to grade the way too: a student who solved well and slipped at the end deserves points, and a right answer with no work may be a guess.

## What Changes

- **The board is saved with every answer**: practice, lesson rounds, lesson quizzes, exercise tests and the simulation. A picture of the question's board goes to the server when the student answers (and again before handing in if it changed). An empty board sends nothing. One picture is kept per student, attempt (or practice) and question.
- **In quizzes and tests the way is required**: a choice is refused until something is written on the board for that question (or a board for it is already saved), with a prompt and a button that opens the board. Practice and lesson rounds stay free.
- **The teacher grades the way**: a "בדיקת דרך" tab lists the handed-in quizzes and tests of the teacher's students (not checked first). Opening one shows every question with its choices (the right one marked), the student's choice and board, and points buttons: automatic, 0, ½, full. Saving recomputes the grade (in halves), so a lesson quiz can become passed or not. The tab counts the attempts not checked yet.
- Work pictures are private: the student and the teachers of the student's classes (and developers) read them. They follow the answer pictures' retention (removed after the school year) and a replaced one is cleaned up as an orphan.

## Capabilities

### New Capabilities
- `board-work`

### Modified Capabilities
- `grades`: a graded attempt's grade includes the teacher's points for the way.

## Impact

- New `mathly2/boardwork.py`, `static/boardwork.js`, `static/teacher_boardwork.js`; `math-board.js` (`hasWork`, `workSig`, `pictureOf`), `exercise.js`, `round.js`, `quiz.js`, `teacher.js`; `attempts.py` (credit in the grade), `store.py` (`save_work`, `work_of`, credit on attempts), `written.py` (who reads a work picture), `cleanup.py`, `assignments.py` (the tab's count).
- Database: migration `20261120090000_m2_board_work.sql` (new `m2_work`, `credit`/`checked_at`/`checked_by` on `m2_attempts`, picture kind `work`). Apply before deploying.
- Storage: one small picture per answer with a board.
