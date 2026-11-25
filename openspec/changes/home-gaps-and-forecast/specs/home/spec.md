## ADDED Requirements

### Requirement: Big buttons on home
The system SHALL show under the status line a big button to the current lesson (a round left open first), and big buttons for quick practice (תרגול מהיר) and a photographed question when available, and SHALL NOT repeat the current lesson in the lessons below.

#### Scenario: A current lesson by date
- **WHEN** the curriculum's current lesson is lesson 3
- **THEN** the first big button opens lesson 3's round and says "השיעור הנוכחי"

### Requirement: Closing the gaps
The system SHALL offer, when lessons are behind the curriculum, a closing-the-gaps round of 5 questions on each lesson behind, the earliest first, and SHALL mark every skill of a lesson answered above 90% as mastered so that it is no longer behind.

#### Scenario: One lesson closed, one not
- **WHEN** a student answers 5 of 5 on one behind lesson and 4 of 5 on another
- **THEN** the first is no longer behind and the next closing-the-gaps round draws only the second

### Requirement: The estimated grade and the days left, encouraging
The system SHALL show the nearest test's days left and estimated grade prominently, with the grade the best 3 good rounds would reach; SHALL show no number before 15 answers on the material; and SHALL show a rise since the last visit but not a dip.

#### Scenario: A low grade
- **WHEN** the estimated grade is 54 and three good rounds would bring it to 63
- **THEN** home shows 54 and "אפשר להגיע ל־63 בעוד 3 סבבים"

#### Scenario: Before enough answers
- **WHEN** the student has answered fewer than 15 questions on the test's material
- **THEN** home shows "?" with how many answers are left, not a number

### Requirement: Pressure that grows as the test nears
The system SHALL show a phase by the days left (more than 14, 8–14, 4–7, 1–3, the day itself) with stronger colours and a daily mission of 1, 1, 2 and 3 rounds with the points they add.

#### Scenario: Two days left
- **WHEN** the test is in 2 days
- **THEN** home shows "ספרינט אחרון!" and a mission of 3 rounds with their points
