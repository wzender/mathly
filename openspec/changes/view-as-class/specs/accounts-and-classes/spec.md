## ADDED Requirements

### Requirement: View the student screens as a class
A developer or a teacher who is in no class as a student SHALL be able to pick a class in "תצוגה ככיתה" on top of the student screens: a developer any class, a teacher only a class they teach. With a class picked, the student screens SHALL show that class's tests, assignments, subjects and photo help; progress, stars and readiness SHALL stay the viewer's own. A pick the person may not make SHALL show nothing of that class, and a student's own classes SHALL never be replaced.

#### Scenario: A developer checks a new test
- **WHEN** a developer opens the student view, picks "ט מצוינות" and opens math
- **THEN** home shows the class's nearest test, and its test page lists the class's other tests

#### Scenario: Another teacher's class
- **WHEN** a teacher sends another teacher's class as the class to view
- **THEN** no test or assignment of that class is shown
