## ADDED Requirements

### Requirement: One screen
The home SHALL fit on one phone screen (360×800) without scrolling, with every lesson of the subject, the nearest test and the new assignments. From top to bottom: the stars collected, the lessons perfected, the streak and the daily goal; the play button; the nearest test's strip; small buttons for a required simulation, the new assignments and photo help; the lessons as a grid of small tiles.

#### Scenario: A full class
- **WHEN** a student whose class studies all 24 lessons, with an upcoming test and a new assignment, opens home on a 360×800 screen
- **THEN** everything is on the screen and nothing scrolls

### Requirement: The lessons board
Each lesson SHALL be a small tile in the bank's order: its number (a crown when it has three stars), its stars as ★ and ☆, its name cut short, "⏰" when it is behind the curriculum and "◐" when a round is open; its accessible name says all of these in words with the full name. Tapping a tile SHALL open the lesson's round over the home.

#### Scenario: A behind lesson
- **WHEN** a lesson's date has passed and it is not completed
- **THEN** its tile shows "⏰" and its name says it is behind and since when

### Requirement: Lessons by date
When the class's curriculum gives lessons dates, home SHALL show the current lesson (the first whose date is today or later, by Israel's date) on its own with its date, and fold under it "שיעורים שעברו" (dates gone by, with how many are behind) and "השיעורים הבאים" (later dates or no date), each with its count. Without dates the lessons stay one grid.

#### Scenario: The middle of the term
- **WHEN** two lessons' dates have passed, one of them not completed, and the next lesson's date is in two days
- **THEN** that lesson is shown as the current one, and "שיעורים שעברו (2)" is folded with "⏰ 1 בפיגור"

### Requirement: Play the next lesson
Home SHALL have one big button that opens the round of the next lesson: the lesson with an open round, else the earliest lesson behind the curriculum, else the first lesson with fewer than three stars. With every lesson perfect, it SHALL say so.

#### Scenario: New student
- **WHEN** a student who answered nothing opens home
- **THEN** the button opens the round of the first lesson

## MODIFIED Requirements

### Requirement: Today's task
The home SHALL show the nearest test in one strip: the days left and the readiness number, opening the test's card (which has the readiness bar, the plan and the practice tests), and today's one task from the countdown plan as a button that opens it.

#### Scenario: Exercise test due
- **WHEN** the nearest test is 9 days away and exercise test 1 is not taken
- **THEN** the strip's button opens exercise test 1

### Requirement: Continue the path
The path SHALL be reached from its tab, "העמקה"; the home has no other link to it.

#### Scenario: No test
- **WHEN** a student has no upcoming test
- **THEN** home shows the stars, the play button and the lessons board

### Requirement: Home shows only what is critical
The home SHALL show only: the stars and goal, the play button, the lessons board, the nearest test's strip, a required simulation, the number of new assignments (as one button to "הגשות") and photo help. Other tests, the readiness bar, the practice tests, assignments that were handed in or checked, and settings SHALL NOT be on home; they are on the test's card and in their tabs.

#### Scenario: Two tests
- **WHEN** a student has two upcoming tests
- **THEN** home shows the nearest one, and the other is listed on that test's card

## REMOVED Requirements

### Requirement: Lessons behind on home
**Reason**: A behind lesson is marked on its tile, and the play button opens the earliest behind lesson first.
**Migration**: None; the quiz stays on the path.

### Requirement: Practice tests below the pass line
**Reason**: The home must fit one screen; the test's card lists the practice tests with their grades.
**Migration**: None.
