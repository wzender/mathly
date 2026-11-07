# Spec Delta

## Purpose

Teaches each skill (מיומנות) through four stages in a fixed order: a worked example, faded examples, practice, and feedback that names the student's mistake, so the student learns to solve alone.

## ADDED Requirements

### Requirement: Worked example with "why this step?"
The system SHALL start a skill with a fully solved example shown one step at a time. After each step, the system SHALL ask the student "why this step?" as a multiple-choice question before revealing the next step.

#### Scenario: Stepping through the example
- **WHEN** a student opens the worked example of פירוק טרינום and sees its first step
- **THEN** a "why this step?" multiple-choice question is shown, and the second step appears only after the student answers it

### Requirement: Faded examples
After the worked example, the system SHALL show solved examples with steps removed: first one step missing, then two, and so on. The student SHALL fill in each missing step. A wrong step SHALL get immediate feedback on the mistake.

#### Scenario: Help fades
- **WHEN** the student finishes the faded example with one missing step
- **THEN** the next faded example has two missing steps

#### Scenario: Wrong step
- **WHEN** the student fills in a missing step wrongly
- **THEN** feedback on the mistake is shown right away

### Requirement: Stages without content are skipped
The system SHALL skip a stage for a skill whose bank entry has no content for it: no worked example skips stage 1, and no faded examples skips stage 2. A skill MUST always be learnable through practice, so a missing example MUST NOT block it.

#### Scenario: Skill with no examples
- **WHEN** a student opens a skill that has no worked example and no faded examples
- **THEN** the skill opens directly at the practice stage

#### Scenario: Worked example but no faded examples
- **WHEN** a student finishes the worked example of a skill that has no faded examples
- **THEN** the skill moves to the practice stage

### Requirement: Practice from the exercise bank
After the faded examples, the system SHALL give the student practice questions on the skill, taken from the exercise bank.

#### Scenario: Practice questions
- **WHEN** the student reaches the practice stage of a skill
- **THEN** the questions shown are exercise-bank questions of that skill

### Requirement: Feedback names the mistake
After a wrong answer in practice, the system SHALL show the name and tip of the mistake attached to the chosen wrong answer in the exercise bank. It MUST NOT reveal the correct answer.

#### Scenario: Wrong choice with a mistake
- **WHEN** a student picks a wrong choice tagged with the mistake "טעות סימן באיבר האמצעי"
- **THEN** the mistake's name and tip are shown, and the correct choice is not marked

### Requirement: Similar question after a mistake
After a wrong answer in practice, the system SHALL give the student a similar question: the same skill, a different question. It MUST NOT give the same question again.

#### Scenario: Next question after a mistake
- **WHEN** a student answers a practice question wrongly
- **THEN** the next question is on the same skill and is not the question just answered
