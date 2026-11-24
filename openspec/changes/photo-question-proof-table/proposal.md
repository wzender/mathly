## Why

Geometry answers have a fixed structure of claims and reasons (טענה/נימוק). Writing it in a table teaches that structure, and typed rows are checked more precisely than handwriting on the board.

## What Changes

- The AI marks a photographed question as a claim/reason question (`proof`) when it reads it; its steps become rows "טענה | נימוק".
- Such a question is solved in a table for each part, with a symbol bar and a list of common reasons; the table is required, the board optional.
- The check reads the table row by row and points to rows; the next-step hint fills the next row; the teacher and the tutor see the handed-in table.

## Impact

`mathly2/photoq.py`, `mathly2/boardreview.py`, `mathly2/static/photoq.js`, `mathly2/static/teacher_photoq.js`, `mathly2/static/app.css`. No migration: the layout and the rows are kept in the question's `review`.
