# Spec Delta

## Purpose

Decides, on the server, which state each skill is in for each student, so mastery is proven by answers over time and never assumed.

## ADDED Requirements

### Requirement: Skill states
Every skill SHALL be, for every student, in exactly one state: not started (no answers yet), learning (at least one answer, not mastered) or mastered.

#### Scenario: First answer
- **WHEN** a student answers the first question of a skill
- **THEN** the skill moves from not started to learning

### Requirement: Mastery rule
A skill SHALL become mastered when the student answers 3 of its questions correctly in a row, each on the first try and without opening help, and these 3 answers fall on at least 2 different calendar days.

#### Scenario: Two days
- **WHEN** a student answers 2 correctly on Monday and 1 correctly on Tuesday, all first try and without help
- **THEN** the skill becomes mastered

#### Scenario: One day
- **WHEN** a student answers 3 correctly in a row on the same day
- **THEN** the skill is still learning

#### Scenario: A wrong answer
- **WHEN** a student answers 2 correctly, then 1 wrongly, then 1 correctly
- **THEN** the run restarts from the last correct answer

### Requirement: Help does not break the run
An answer given after the student opened help on that question SHALL be skipped for mastery: it neither counts toward the 3 nor breaks the run.

#### Scenario: Help between correct answers
- **WHEN** a student answers 2 correctly on Monday, a third with help, and a fourth correctly on Tuesday without help
- **THEN** the skill becomes mastered

### Requirement: Mastery does not decay
A mastered skill SHALL stay mastered, even after later wrong answers or months without practice.

#### Scenario: Months later
- **WHEN** a student who mastered a skill in October answers a question on it wrongly in March
- **THEN** the skill is still mastered

### Requirement: Answers are dated by the server
Every answer SHALL be stored with the server's calendar day in Israel, and mastery SHALL be decided from these days.

#### Scenario: Device clock changed
- **WHEN** a student changes the device's date before answering
- **THEN** the answer is dated by the server, and mastery uses that date
