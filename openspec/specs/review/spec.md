# review Specification

## Purpose
The student's review list (חזרה): every wrong answer waits there as a card, grouped by skill, answered in place; practice only, counted toward the daily goal.

## Requirements

### Requirement: Wrong answers go to חזרה
Every wrong answer SHALL be added to the student's חזרה list: in path practice, in a lesson בוחן, in a practice test and in the simulation. A question left unanswered when a בוחן or a test is submitted or its time ends SHALL be added as well. A question already in the list SHALL not be added again.

#### Scenario: A wrong practice answer
- **WHEN** a student answers a practice question wrongly
- **THEN** the question is in their חזרה list

#### Scenario: A בוחן
- **WHEN** a student submits a בוחן with two wrong answers and one unanswered question
- **THEN** all three questions are in their חזרה list

#### Scenario: Twice
- **WHEN** a student gets the same question wrong again
- **THEN** it is in the list once

### Requirement: The חזרה tab
The student's tab bar SHALL have a "חזרה" tab. It SHALL show how many questions wait and show every waiting question as a card with its choices, grouped by skill: a heading per skill with its lesson and the number of cards, the skills in the bank's order and each skill's cards oldest first. A skill with no waiting question SHALL have no heading. An empty list SHALL say so. The tab MUST be reachable on a phone without sideways scrolling.

#### Scenario: Questions waiting
- **WHEN** a student with five questions on two skills opens חזרה
- **THEN** it says five wait and shows two skill headings with their cards under them

#### Scenario: Empty
- **WHEN** the list is empty
- **THEN** the tab says there is nothing to review

#### Scenario: Order
- **WHEN** a skill has three waiting questions
- **THEN** its cards are in the order the mistakes were made, the oldest first

### Requirement: Redoing a question
A card SHALL be answered in place. A right answer SHALL remove the question from the list and mark the card done. A wrong answer SHALL keep it, name the mistake and show its tip, MUST NOT show the right choice, and SHALL offer "נסו שוב". The right choice MUST NOT be sent to the page before the answer.

#### Scenario: Right
- **WHEN** a student answers a card correctly
- **THEN** the card is marked done, the question leaves the list, and the counts of the page and of its skill go down by one

#### Scenario: The last card of a skill
- **WHEN** the last waiting card of a skill is answered correctly
- **THEN** that skill's heading goes away

#### Scenario: Wrong
- **WHEN** they answer a card wrongly
- **THEN** it stays, the mistake's name and tip show, the right choice is not shown, and "נסו שוב" lets them answer again

### Requirement: Practice only
Redoing a question in חזרה SHALL NOT change any skill's mastery, any grade or the readiness meter, and SHALL NOT change which questions a practice round has left. Each right answer SHALL count toward the daily goal.

#### Scenario: Mastery
- **WHEN** a student answers ten questions right in חזרה on a skill they have not mastered
- **THEN** the skill is not mastered because of them

#### Scenario: The daily goal
- **WHEN** a student answers a question right in חזרה
- **THEN** today's correct answers go up by one
