## ADDED Requirements

### Requirement: Activity chart
The developer's home SHALL show, below the status card, how many different people were active on each Israel calendar day of the last 7 days, or of the last 30 days when chosen, with days without activity shown as zero. A person is active on a day when they answered a practice question or started a quiz or a test that day, and SHALL be counted once that day however much they did. The card SHALL also show today's count and the number of different people over the whole range. Only counts SHALL be returned, never who was active, and only a developer can read them.

#### Scenario: A week of activity
- **WHEN** one student answered two questions today and another answered one two days ago
- **THEN** today's column shows 1, the column two days ago shows 1, and the week shows 2 different people

#### Scenario: Late at night
- **WHEN** a student starts a quiz at 00:30 Israel time
- **THEN** it counts on that Israel day, not on the day before in UTC

#### Scenario: A month
- **WHEN** the developer chooses 30 days
- **THEN** the chart has 30 columns and the total counts different people over the 30 days
