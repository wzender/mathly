## ADDED Requirements

### Requirement: Written answers
The simulation SHALL show no choices. Each question SHALL be answered on its board. When the right answer is a plain number, possibly with a variable ("x = 5"), a degree sign or a fraction, the question SHALL also have a box for the final answer; other questions SHALL be answered on the board only. A question SHALL count as answered when its board has work or its box has an answer, and only the board's work earns points.

#### Scenario: A plain-number answer
- **WHEN** a simulation question's right answer is "x = 5"
- **THEN** the question shows a box labelled "x =" beside the board button, and no choices

#### Scenario: An expression
- **WHEN** a question's right answer is "x² + 4x + 4"
- **THEN** it has no box and is answered on the board

### Requirement: Checked by the AI
After the hand-in, the AI SHALL check each board with work: given the question, the right answer (never shown to the student) and the typed final answer with whether it matches, it gives "correct" (1 point), "partial" (½), "wrong" or "unclear" (0). A question with an empty board SHALL be 0. Once every board with work has a verdict, the grade SHALL be the points' share, rounded, and the questions without full points SHALL go to the review list.

#### Scenario: Three boards
- **WHEN** a student writes on three of twelve boards and the AI judges them correct, partial and wrong
- **THEN** the grade is 1½ of 12 points, 13

### Requirement: Waiting for the check
Until it is checked, a handed-in simulation SHALL show "בבדיקה" and no grade; it SHALL count as taken but SHALL NOT move the readiness number, appear as a grade, or offer the mistakes round. Without the AI, or when the check fails, it SHALL say it waits for the teacher's check.

#### Scenario: No AI
- **WHEN** a student hands in a simulation and no AI key is set
- **THEN** the result says it waits for the teacher, and the readiness number does not change

### Requirement: The teacher's check
The teacher SHALL see each question with the right answer, the typed final answer (and whether it matches), the board and the AI's verdict, and MAY give 0, ½ or full points. The teacher's points SHALL replace the AI's; the teacher's check SHALL be final, and a board with neither SHALL count 0.

#### Scenario: Checked by the teacher
- **WHEN** the teacher gives one question full points on a simulation the AI did not check
- **THEN** its grade is set at once, counting the other boards as 0
