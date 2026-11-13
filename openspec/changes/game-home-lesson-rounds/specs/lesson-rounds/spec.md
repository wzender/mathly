## ADDED Requirements

### Requirement: A lesson round
Every lesson with practice questions SHALL have a round of at most 10 questions drawn from its skills that are not mastered, at most 3 from each, spread evenly, the least-used questions first. When every skill of the lesson is mastered the round SHALL draw 10 from all its skills. Starting a round while one is open SHALL resume it.

#### Scenario: Five skills, none mastered
- **WHEN** a student starts the round of a lesson with five skills and none mastered
- **THEN** it has 10 questions, 2 from each skill

#### Scenario: One skill left
- **WHEN** four of the lesson's five skills are mastered
- **THEN** the round has 3 questions, all from the fifth skill

### Requirement: Instant feedback in a round
Each answer in a round SHALL be graded at once, with the same feedback as the exercise screen: a celebration for a right answer, the mistake's name and tip for a wrong one, never the right choice. The questions SHALL be answered in order, each once. Every answer SHALL be stored as a practice answer of its skill, not given with help, so it counts for mastery and the daily goal, and a wrong one goes to the review list.

#### Scenario: Mastery from a round
- **WHEN** a student answered a skill's last two questions right yesterday and answers its question in today's round right
- **THEN** the skill becomes mastered and the answer's feedback says so

### Requirement: A round's result
After the last answer the round SHALL show the right answers out of its questions, the lesson's stars, the skills mastered in it, the skills that are one good day away from mastery, and each mistake's name and tip. It SHALL offer another round and a way back home.

#### Scenario: Seven of ten
- **WHEN** a student finishes a round with 7 right
- **THEN** the result shows "7 מתוך 10", one star, and the three mistakes

### Requirement: Stars per lesson
A lesson SHALL have 0 to 3 stars: 3 when every one of its skills is mastered; else 2 when a finished round had at least 80% right; else 1 when a round was finished; else 0. Stars never go down.

#### Scenario: Eight of ten
- **WHEN** a student finishes a lesson's round with 8 right and some skills not mastered
- **THEN** the lesson has two stars
