# Spec Delta

## Purpose

Gives every lesson a retakeable quiz (בוחן) whose best grade is the lesson's grade, and points the student to the skills to practise before retaking it.

## ADDED Requirements

### Requirement: Quiz per lesson
Each lesson SHALL have a quiz on that lesson. It SHALL be the only quiz type; there MUST NOT be a one-time summary quiz.

#### Scenario: Opening a lesson's quiz
- **WHEN** a student opens the quiz of טכניקה אלגברית 1
- **THEN** its questions are on that lesson's skills

### Requirement: Retakes draw new questions
The student SHALL be able to retake a quiz any number of times. Each retake SHALL draw new questions.

#### Scenario: Second attempt
- **WHEN** a student retakes a lesson's quiz
- **THEN** the questions are drawn anew rather than repeating the previous attempt's set

### Requirement: Best grade is the lesson's grade
The quiz grade that counts SHALL be the student's best grade across attempts, and it SHALL be the lesson's grade.

#### Scenario: Lower retake
- **WHEN** a student got 85 and then 70 on a lesson's quiz
- **THEN** the lesson's grade is 85

### Requirement: Skills to practise after a quiz
After a quiz, the system SHALL list the skills where the student lost points, so they can practise them before retaking.

#### Scenario: Lost points
- **WHEN** a student loses points on questions of 2 skills
- **THEN** the result lists those 2 skills

### Requirement: Quiz grades kept on the server
Quiz grades SHALL be computed and stored on the server, so a student cannot change them from the device.

#### Scenario: Handing in
- **WHEN** a student hands in a quiz
- **THEN** the server computes and stores the grade
