# Spec Delta

## MODIFIED Requirements

### Requirement: Setting a test
The teacher of a class SHALL be able to set a test for it: a subject the class studies, a date, the lessons it covers (from that subject's lessons), an optional note, the number of questions and the time limit. A test MUST NOT cover lessons of two subjects. The number of questions SHALL default to 12 and the time limit to 45 minutes; both can be changed.

#### Scenario: Defaults
- **WHEN** a teacher sets a test without changing the number of questions or the time
- **THEN** the test has 12 questions and 45 minutes

#### Scenario: A test of another subject
- **WHEN** a teacher of a class studying math and "מדעים" sets a "מדעים" test
- **THEN** only "מדעים" lessons can be chosen, and the test appears on the students' "מדעים" home only

#### Scenario: Lessons of two subjects
- **WHEN** a request sets a test covering a math lesson and a "מדעים" lesson
- **THEN** the server refuses it and says a test covers one subject
