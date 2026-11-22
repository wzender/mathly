## ADDED Requirements

### Requirement: Each student's activity
The progress tab SHALL have a "פעילות" view for the class's teacher and the developer: for each student, over the last 7, 14 or 30 days, the exercises (every practice answer), the estimated time, the active days and the share right; since the school year began, the exercises and the time; and the last active day. The days SHALL show as small bars that open a day-by-day table with the exercises, the share right, the time and the quizzes and tests handed in.

#### Scenario: A student who practised twice
- **WHEN** a student answered 6 questions today and 1 two days ago
- **THEN** the view shows 7 exercises on 2 days over the range, and today's row in the day-by-day table

### Requirement: Time spent
Time SHALL be estimated: within a day, the gap since the previous answer counts up to 3 minutes, a gap of more than 5 minutes is a break, and the first answer after a break (or of the day) counts 1 minute; a quiz or test counts from its start to its hand-in, at most 2 hours.

#### Scenario: A break
- **WHEN** a student answers at 0, 30, 90, 690 and 710 seconds
- **THEN** the time is 60 + 30 + 60 + 60 + 20 seconds
