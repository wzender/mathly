# rewards Specification

## Purpose
Rewards that bring a student back to practice: a daily goal and streak, stars that fade when neglected, a collection of what they achieved, and rare comets to catch. None of them changes a skill's state or a grade.

## Requirements

### Requirement: Daily goal
A day with 5 correct answers SHALL be a streak day. The path SHALL show today's count toward 5. Answers given after opening help SHALL count toward the goal.

#### Scenario: Goal reached
- **WHEN** a student answers a fifth question correctly today
- **THEN** today's goal shows as reached

### Requirement: Streak
The path SHALL show the number of streak days in a row. Until today's 5 are reached, the streak SHALL be counted up to yesterday and shown as still alive.

#### Scenario: Morning
- **WHEN** a student with a 4-day streak opens the app in the morning with no answers yet today
- **THEN** the streak still shows 4

#### Scenario: Missed day
- **WHEN** a student had no streak day yesterday
- **THEN** the streak starts again from today

### Requirement: Fading stars
A mastered skill the student has not answered for 14 days SHALL show a faded star that says "דועך". One answer on that skill SHALL relight it. Fading MUST NOT change the skill's state, the readiness meter, the heat map or the exercise tests.

#### Scenario: Two weeks
- **WHEN** a student has not answered a mastered skill for 15 days
- **THEN** its star is dimmed with "דועך", and the skill still counts as mastered

#### Scenario: Relighting
- **WHEN** the student answers one question of that skill, right or wrong
- **THEN** the star is bright again

### Requirement: Collection
A collection screen SHALL show each mastered skill as a star and each completed lesson (all its skills mastered) as a constellation drawn from its stars.

#### Scenario: Completed lesson
- **WHEN** a student masters the last skill of a lesson
- **THEN** that lesson's constellation appears in the collection

### Requirement: Comets cross
After a right answer on the exercise screen a comet MAY cross the screen for a few seconds, at most once a day. The first comet SHALL come the first time the student reaches the daily goal; afterwards each right answer has a chance of about 12% while comets are left to catch.

#### Scenario: First daily goal
- **WHEN** a student reaches the daily goal for the first time ever
- **THEN** a comet crosses the screen

#### Scenario: Once a day
- **WHEN** a student already saw a comet today
- **THEN** no other comet comes today

### Requirement: Catching comets
Tapping a crossing comet SHALL catch it: a comet the student does not have yet, at random, shown with its name and fact. There SHALL be twelve: π, Fibonacci, the golden ratio, infinity, e, √2, zero, Pythagoras, primes, Pascal's triangle, Euler's formula and the Möbius strip. Comets stop when all are caught.

#### Scenario: Catch
- **WHEN** a student taps a crossing comet
- **THEN** a comet they did not have is added to their collection with its fact

### Requirement: Comets in the collection
The collection SHALL show every caught comet with its symbol, name and fact, and every missing one as "?" with "עוד לא נתפס".

#### Scenario: Three caught
- **WHEN** a student caught three comets
- **THEN** the collection shows three comets and nine "?"

### Requirement: Comets with reduced motion
With reduced motion a comet SHALL NOT cross the screen; the student SHALL be offered it once as a tappable item instead.

#### Scenario: Reduced motion
- **WHEN** a comet is due and the device asks for reduced motion
- **THEN** a still comet button appears once instead of a moving comet
