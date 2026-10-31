# Spec Delta

## Purpose

Allow students to answer questions requiring handwritten reasoning or drawings and retain a private photographed answer on the correct question attempt.

## ADDED Requirements

### Requirement: Open-ended question presentation
The system SHALL support open-ended questions without predefined answer options and SHALL offer “Scan my answer with my phone” on those questions, using localized text where appropriate.

#### Scenario: Open a geometry question
- **WHEN** a student opens an open-ended geometry question
- **THEN** the question and any diagram appear without answer-choice controls
- **AND** the student can initiate a phone scan

#### Scenario: Existing choice question
- **WHEN** a student opens an existing multiple-choice question
- **THEN** its answer choices and feedback continue to work

### Requirement: Stable student question attempts
The system SHALL give each open-ended attempt a stable identity owned by the authenticated student and bound to the question and its content version. The system SHALL verify ownership before creating a scan or attaching an answer.

#### Scenario: Resume the same attempt
- **WHEN** the student reloads an open-ended question with an active attempt
- **THEN** the system restores that attempt and its scan or attached answer

#### Scenario: Reject a foreign or mismatched attempt
- **WHEN** a student requests a scan using another student's attempt or a different question identifier
- **THEN** the system rejects the request without revealing the other student's data

### Requirement: Private durable answer attachment
The system SHALL retain a submitted photograph as an answer attachment to its original student, question, and attempt. Only that student SHALL be able to retrieve the photograph through the student-facing flow. Upload confirmation SHALL occur only after both image storage and attachment persistence succeed.

#### Scenario: Submission succeeds
- **WHEN** a confirmed scan submission completes successfully
- **THEN** the photograph appears on its original question attempt on the computer
- **AND** both devices confirm successful upload

#### Scenario: Navigate to another question
- **WHEN** the student changes questions before an upload completes
- **THEN** the received answer remains attached exclusively to the original attempt

#### Scenario: Restart after submission
- **WHEN** the server restarts and the student reopens a submitted attempt
- **THEN** the saved answer remains accessible to its owner

#### Scenario: Photograph access by another account
- **WHEN** another account requests an attachment or its image
- **THEN** access is denied without revealing the attachment contents

### Requirement: Submission does not imply correctness
The system SHALL distinguish answer receipt from grading and SHALL NOT mark an open-ended answer correct or a skill mastered solely because a photograph was uploaded.

#### Scenario: Answer received without grading
- **WHEN** a photograph is attached successfully
- **THEN** the attempt displays an answer-received state without automatically awarding correctness or mastery
