# Spec Delta

## Purpose

Uses one pair of names on every student and teacher screen: a בוחן (quiz) can be retaken and its best grade counts, a מבחן (exam) is handed in once. Students and teachers can then tell at a glance what kind of test they are looking at.

## ADDED Requirements

### Requirement: Quiz and exam names
Every test a student can retake SHALL be called "בוחן", and every test handed in once SHALL be called "מבחן", on student and teacher screens and in the user guide. A practice unit-quiz sitting SHALL be a בוחן, a final one a מבחן. The mixed practice test SHALL be a בוחן. School exams on the exam table SHALL stay "מבחן".

#### Scenario: Final unit quiz
- **WHEN** the teacher opened the final unit quiz of `k` and a student sees it in their task list
- **THEN** it is named "מבחן: דלתון", and the start button reads "התחלת המבחן"

#### Scenario: Practice unit quiz
- **WHEN** a student opens the practice unit quiz of `k`
- **THEN** it is titled "בוחן מסכם", with the unit's name "דלתון" next to the title

#### Scenario: Old names gone
- **WHEN** any student or teacher screen is shown
- **THEN** none of "בוחן סופי", "בוחן תרגול" or "מבחן תרגול" appears

### Requirement: A quiz shows its best grade
For a practice unit quiz, the grade shown to the student and on their grades page SHALL be their best handed-in grade, with the latest shown next to it when different. The official grade of a unit SHALL stay the grade of the latest handed-in final sitting.

#### Scenario: Best and latest
- **WHEN** a student got 85 and then 70 in practice sittings of unit `k`
- **THEN** the grades page shows "בוחן: 85" with "אחרון: 70"

#### Scenario: Official grade unchanged
- **WHEN** the student got 62 in the final sitting of `k` and 90 in a later practice sitting
- **THEN** the official grade of `k` stays 62, shown as "מבחן: 62"
