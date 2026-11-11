# Spec Delta

## MODIFIED Requirements

### Requirement: A date per lesson
The course SHALL have one curriculum for the whole school: each lesson MAY have a date by which it should be completed. A manager (or a developer) SHALL set, change and clear these dates in a "תכנית לימודים" tab of the manager screen, which lists every published lesson grouped by subject, each subject's lessons in its order, with its date. Nobody else SHALL be able to change them. A lesson with no date SHALL never count as behind.

#### Scenario: Setting dates
- **WHEN** a manager enters 3.11 for the first lesson and saves
- **THEN** the curriculum tab shows 3.11 for that lesson, and students' paths use it

#### Scenario: Clearing a date
- **WHEN** a manager clears a lesson's date and saves
- **THEN** the lesson has no date and no student sees it as behind

#### Scenario: Not a manager
- **WHEN** a teacher or a student asks to change a date
- **THEN** the server refuses and nothing changes

#### Scenario: Two subjects
- **WHEN** a manager opens the curriculum tab while math and "מדעים" have published lessons
- **THEN** the lessons are listed under a "מתמטיקה" heading and a "מדעים" heading
