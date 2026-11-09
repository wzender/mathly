## ADDED Requirements

### Requirement: Slow-changing facts are remembered briefly
The server SHALL remember the classes, their students, the roles, the tests and the assignments for at most 30 seconds, so a screen that needs them does not wait for the database again. Any change made through the app to one of them SHALL make the server forget the remembered copy at once. The time SHALL be a setting, and 0 SHALL turn it off.

#### Scenario: Opened again
- **WHEN** a teacher opens the assignments tab twice within 30 seconds and every database call takes 0.1 seconds
- **THEN** the second time needs fewer waits in a row than the first

#### Scenario: A change
- **WHEN** a teacher gives an assignment and then opens the assignments tab
- **THEN** the new assignment is there, not an old remembered list

### Requirement: A screen shows what it last knew
A screen opened again SHALL show the data it last had at once and refresh it in the background; the tab numbers of a teacher's screen SHALL show their last values at once. After a change the person made, nothing remembered SHALL be shown: the screen waits for fresh data. A refresh MUST NOT redraw the screen while the person is typing in it or has something open.

#### Scenario: Back to a tab
- **WHEN** a teacher goes to another tab and back, and the server takes two seconds to answer
- **THEN** the tab shows its last content and numbers at once, and shows the new ones when they arrive

#### Scenario: After grading
- **WHEN** a teacher grades a submission and the inbox is shown again
- **THEN** the graded submission is not in it, not even for a moment

#### Scenario: Typing
- **WHEN** fresh data arrives while a teacher is typing in a form on the screen
- **THEN** what they typed is still there
