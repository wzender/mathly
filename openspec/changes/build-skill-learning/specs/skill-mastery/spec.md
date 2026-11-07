# Spec Delta

## Purpose

Defines when a skill counts as mastered and the state every skill is in for every student, so mastery is proven rather than assumed and stays once earned.

## ADDED Requirements

### Requirement: Mastery rule
A skill SHALL become mastered when the student answers 3 questions on it correctly in a row, each on the first try, without opening help or the worked example, and these answers are spread over at least 2 different calendar days.

#### Scenario: Mastered over two days
- **WHEN** a student answers 2 questions of a skill correctly on Monday and a third correctly on Tuesday, all first try and without help
- **THEN** the skill becomes mastered

#### Scenario: All on one day
- **WHEN** a student answers 3 questions of a skill correctly in a row on the same day
- **THEN** the skill is not yet mastered

#### Scenario: Help opened
- **WHEN** a student opens help or the worked example before answering a question
- **THEN** that answer is skipped for mastery: it neither counts toward the run nor breaks it

#### Scenario: Help between correct answers
- **WHEN** a student answers 2 questions correctly without help on Monday, answers a third with help, and answers a fourth correctly without help on Tuesday
- **THEN** the skill becomes mastered, since the run of counted answers is the Monday, Monday and Tuesday ones

#### Scenario: Streak broken
- **WHEN** a student answers 2 correctly, then 1 wrongly, then 1 correctly
- **THEN** the run of correct answers in a row restarts from the last correct answer

### Requirement: Skill states
Every skill, for every student, SHALL be in exactly one state: "not started" (no answers yet), "learning" (at least one answer, not yet mastered) or "mastered" (met the mastery rule).

#### Scenario: First answer
- **WHEN** a student answers the first question of a skill
- **THEN** the skill moves from "not started" to "learning"

### Requirement: Mastery does not decay
A mastered skill SHALL stay mastered. It MUST NOT fade, decay or require re-mastering over time, even after later wrong answers.

#### Scenario: Months later
- **WHEN** a student mastered a skill in October and answers a question on it wrongly in March
- **THEN** the skill is still mastered

### Requirement: Mastery is checked on the server
The server SHALL store the date of each answer and decide mastery from it, so the "2 different days" rule cannot be changed from the device.

#### Scenario: Device clock changed
- **WHEN** a student changes the device date before answering
- **THEN** the answer is dated by the server, and mastery uses that date
