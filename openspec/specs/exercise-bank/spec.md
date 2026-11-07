# exercise-bank Specification

## Purpose

Defines the exercise bank kept from the current app as the source of lessons, skills, questions and mistakes, and how its math is shown.

## Requirements

### Requirement: Bank is the content source
Lessons, skills, multiple-choice questions and mistakes SHALL come from the exercise bank kept from the current app. Each wrong choice of a question SHALL point to a mistake with a name, a tip and the skill to go back to.

#### Scenario: Wrong choice
- **WHEN** a student picks a wrong choice
- **THEN** the mistake it points to supplies the feedback's name and tip

### Requirement: Math is rendered
Math written in LaTeX inside `$…$` in the bank SHALL be rendered as math in the app.

#### Scenario: Question with math
- **WHEN** a question's text contains `$x^2+5x+6$`
- **THEN** the student sees it as a formatted formula

### Requirement: Content gaps are filled before use
Worked examples, faded examples, "why this step?" choices and quizzes for every lesson SHALL be added to the bank, since it lacks them today. Each skill SHALL have enough questions for similar questions and for retakes that draw new questions.

#### Scenario: Skill without a worked example
- **WHEN** a skill has no worked example in the bank yet
- **THEN** it is listed as a content gap to fill
