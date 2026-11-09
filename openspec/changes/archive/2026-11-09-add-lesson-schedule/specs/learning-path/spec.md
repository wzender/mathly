## ADDED Requirements

### Requirement: A completed lesson
A lesson SHALL be completed when every one of its skills is mastered, or when its quiz was passed. Passing the quiz MUST NOT change any skill's state. A completed lesson SHALL be marked on its hub with the word "הושלם".

#### Scenario: By skills
- **WHEN** a student has mastered all five skills of a lesson
- **THEN** the lesson is marked completed

#### Scenario: By the quiz
- **WHEN** a student passes a lesson's quiz while two of its skills are still in learning
- **THEN** the lesson is marked completed, and the two skills are still in learning

#### Scenario: Neither
- **WHEN** a student has mastered four of five skills and has not passed the quiz
- **THEN** the lesson is not completed

### Requirement: Lessons behind the curriculum
A lesson that has a date in the curriculum, whose date has passed and that is not completed SHALL be marked on the path as behind, with a marker and its date in words ("היה אמור להסתיים ב־3.11"). The path SHALL say how many lessons are behind. A lesson with no date, a date still ahead, or a completed lesson MUST NOT be marked. Nothing SHALL be locked.

#### Scenario: Behind
- **WHEN** a lesson's date was yesterday and the student has not completed it
- **THEN** its hub shows the behind marker and the date, and the path says "1 שיעורים בפיגור"

#### Scenario: Completed in time
- **WHEN** a lesson's date has passed and the student passed its quiz
- **THEN** the lesson is marked completed and not behind

#### Scenario: Date still ahead or none
- **WHEN** a lesson's date is next week, or it has none
- **THEN** it is not marked behind
