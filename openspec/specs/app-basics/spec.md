# app-basics Specification

## Purpose

Sets the rules every Mathly screen follows: Hebrew right-to-left, phone first, and grades kept on the server.

## Requirements

### Requirement: Hebrew, right-to-left, phone first
Every screen SHALL be in Hebrew, laid out right-to-left, and designed for phones first.

#### Scenario: Opening on a phone
- **WHEN** a student opens the app on a phone
- **THEN** the screen is in Hebrew, right-to-left, and fits the phone's width

### Requirement: Grades that count are kept on the server
Quiz, exercise test and simulation grades SHALL be computed and stored on the server, so a student cannot change them from the device.

#### Scenario: Tampered device
- **WHEN** a student changes a grade stored on their device
- **THEN** the grade shown to them and the teacher is still the server's grade
