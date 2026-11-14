## ADDED Requirements

### Requirement: The board goes with every answer
When a student answers a question in practice, a lesson round, a lesson quiz, an exercise test or the simulation, and the question's board has anything on it besides the copy of the question, a picture of the board SHALL be saved with the answer. Before handing in a quiz or a test, the boards that changed since they were saved SHALL be saved again. An empty board SHALL save nothing. Only the latest picture per student, attempt (or practice) and question SHALL be kept.

#### Scenario: A lesson round
- **WHEN** a student writes on the board and answers a question of a lesson round
- **THEN** the board's picture is saved for that round and question

#### Scenario: No board in practice
- **WHEN** a student answers a practice question without writing on the board
- **THEN** the answer is accepted and no picture is saved

### Requirement: The way is required in quizzes and tests
In a lesson quiz, an exercise test and the simulation, a choice SHALL NOT be saved until the question's board has something written on it or a board for it is already saved. The sheet SHALL say that the way is graded too and offer a button that opens the board.

#### Scenario: Choosing first
- **WHEN** a student taps a choice in a quiz with nothing on the board for that question
- **THEN** the choice is not saved, and the sheet asks to write the way on the board and offers to open it

### Requirement: The teacher grades the way
A teacher SHALL have a "בדיקת דרך" tab with the handed-in quizzes, exercise tests and simulations of the students of their classes, those not checked yet first, and its count of those not checked. Opening one SHALL show every question with its choices, the right one marked, the student's choice and board (or that there is none), and points: automatic (1 for right, 0 for wrong), 0, ½ or full. Saving SHALL recompute the attempt's grade from the points and mark it checked.

#### Scenario: Half for the way
- **WHEN** a student got 12 of 15 right and the teacher gives a wrong answer full points and another half
- **THEN** the grade becomes 90 and the lesson's grade follows

#### Scenario: Another teacher
- **WHEN** a teacher who does not teach the student opens the attempt or its board
- **THEN** it is not found

### Requirement: Private work pictures
A work picture SHALL be read only by its student, the teachers of the student's classes and developers, through the server. Work pictures SHALL be removed after the school year, like answer pictures, and a replaced one SHALL be removed by the hourly cleanup.

#### Scenario: A new board for the same question
- **WHEN** a student saves a second board for a question
- **THEN** the first picture is no longer referred to and the cleanup removes it

### Requirement: An AI review of the way in tests
When a practice test or the simulation is handed in and the server has a Gemini key, the boards of its questions SHALL be sent to the model in one request, with each question, its choices, the right choice (for the model only) and the student's choice, and nothing that names the student. The model SHALL judge the way per question (correct, partial, wrong, unclear) and write a short feedback line and a tip in Hebrew without stating the right answer. The result screen SHALL show "משוב על הדרך": waiting while it is written, then the summary and each reviewed question; if it fails, it says so. The teacher SHALL see the review beside each board, as a suggestion; the points stay the teacher's. A lesson quiz is not reviewed, and without a key there is no review.

#### Scenario: A practice test with two boards
- **WHEN** a student hands in a practice test with boards on questions 1 and 2
- **THEN** one request reviews both, and the result shows the feedback for questions 1 and 2

#### Scenario: Lost by a restart
- **WHEN** a review is still pending ten minutes later
- **THEN** reading the result starts it again
