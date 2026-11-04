# Spec Delta

## Purpose

Gives a student who does not know how to solve a skill's questions a way to learn the method inside the app, at the moment they are stuck, without giving away the answer to the question in front of them.

## ADDED Requirements

### Requirement: Skills have a worked example
Each skill with multiple-choice questions SHALL have a worked example: a question that is not one of the skill's own questions, its solution as ordered steps each with a short explanation, and the final answer. The skills data MUST fail validation when an example repeats one of the skill's questions or has no steps.

#### Scenario: Valid example
- **WHEN** the skills data is loaded and skill `t_ext` has an example with its own question and three steps
- **THEN** loading succeeds and the skills API returns the example with the skill

#### Scenario: Example copies a practice question
- **WHEN** a skill's example question is the same as one of its practice questions
- **THEN** validation of the skills data fails, naming the skill

### Requirement: Example offered after repeated mistakes
In skill practice, the feedback for the second or later wrong answer in the same skill within the current round SHALL offer to open the skill's worked example. The first wrong answer SHALL show only the misconception tip, as today.

#### Scenario: First mistake
- **WHEN** a student makes their first wrong answer in a round of `t_ext`
- **THEN** the feedback shows the misconception name and tip and does not offer the example

#### Scenario: Second mistake
- **WHEN** the same student makes a second wrong answer in that round
- **THEN** the feedback also shows a button "איך פותרים? דוגמה פתורה"

### Requirement: Example opens without losing the question
Opening the worked example SHALL show it inside the skill sheet, step by step, and closing it SHALL return to the same question in the same state. It MUST NOT reveal the answer to the student's current question.

#### Scenario: Open and return
- **WHEN** the student opens the example and then closes it
- **THEN** they are back on the same question, with the same feedback shown

### Requirement: Help is available on demand
The skill sheet SHALL offer a help control at any time that shows the skill's description, its worked example and the teacher's visible resources for that skill.

#### Scenario: Student asks for help before answering
- **WHEN** a student opens skill `t_ext` and presses the help control before answering
- **THEN** the help panel shows the description and the worked example

### Requirement: Example use is recorded
Each time a student opens a skill's worked example, the student's progress SHALL record it for that skill (count and last time). Opening the example MUST NOT change whether the skill is finished or gold.

#### Scenario: Example then correct answers
- **WHEN** a student opens the example of `t_ext` and then answers the remaining questions correctly
- **THEN** the use is recorded for `t_ext`, and finishing and gold follow the same rules as without the example

### Requirement: Teacher sees where examples were used
The class report SHALL show, on each student's card, the skills in which the student opened the worked example in the last 14 days.

#### Scenario: Report card
- **WHEN** a student opened the example of `g_pyth` three times this week
- **THEN** their card lists `g_pyth` among the skills where they used an example
