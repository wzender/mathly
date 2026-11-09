## MODIFIED Requirements

### Requirement: One question at a time
The sheet SHALL show one question: its text with formulas, its figure or graph if any, and its choices in a new random order each time it is shown, with "question n of N" and a row of dots for the skill's practice questions. Practice SHALL use at most 10 questions per skill, the first 10 of the skill's questions in the bank, so N is never more than 10; the skill's other questions stay available to quizzes and tests.

#### Scenario: Same question again
- **WHEN** a question is shown a second time
- **THEN** its choices may be in a different order, and the server still grades by the bank's choice

#### Scenario: A skill with 30 questions
- **WHEN** a student opens a skill that has 30 questions in the bank
- **THEN** the sheet says "question n of 10" and shows 10 dots, and only those 10 questions come up in practice
