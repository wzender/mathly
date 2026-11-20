## ADDED Requirements

### Requirement: The next step
The first thing under home's status line SHALL be one card that links to the exercise to do now and says in one line why it moves the student forward, with the reward and what it costs (minutes and questions, and 🎯 when it completes today's goal). It SHALL replace the play button and home SHALL stay one screen.

#### Scenario: A test further away
- **WHEN** a student's nearest test is in 30 days
- **THEN** the card offers the round of the lesson that moves the forecast most toward the next league, with "+N"

### Requirement: Which step
The step SHALL be, in order: a round already open; a skill whose next right answer today masters it; the earliest lesson behind the curriculum; with a test within 14 days, the weakest lesson of its material with about how many of its questions it is; with a test further away, the lesson whose good round raises the forecast most; else the map's next lesson.

#### Scenario: One answer from a crown
- **WHEN** a student answered a skill right twice yesterday
- **THEN** the card offers that skill: one more right answer and it is mastered
