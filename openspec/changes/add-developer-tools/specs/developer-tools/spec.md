# Spec Delta

## Purpose

Tools only developers can reach: a teleprompter for their texts, a lab for testing tools, and a view of what the AI costs.

## ADDED Requirements

### Requirement: Developers only
The prompter, the lab and the AI usage page SHALL be reachable only by developers.

#### Scenario: Manager
- **WHEN** a manager asks for the prompter
- **THEN** it is refused

### Requirement: Prompter texts
A developer SHALL save texts (a title up to 120 characters, up to 200 texts) that belong to their account and appear on every device. The text being edited SHALL also be kept in the browser until it is saved.

#### Scenario: Another device
- **WHEN** a developer saves a text on a computer and opens the prompter on a tablet
- **THEN** the text is there

### Requirement: Prompter screen
The prompter SHALL show a text full screen and scroll it. Space starts and stops, ↑/↓ change speed, +/− change size, M mirrors, F is full screen and Esc leaves; the mouse and a presentation remote SHALL work too.

#### Scenario: Mirror
- **WHEN** a developer presses M during scrolling
- **THEN** the text is shown mirrored

### Requirement: Outline
On request the AI SHALL write a saved text's outline: the same slides with two to four very short topic reminders each, kept with the text and editable. Changing the text without sending an outline SHALL drop the outline.

#### Scenario: Text changed
- **WHEN** a developer edits a text that has an outline and saves only the text
- **THEN** the outline is removed

### Requirement: Lab
The lab SHALL be a page for testing and development tools. Until the first tool is chosen it SHALL say that tools will be added here.

#### Scenario: Empty lab
- **WHEN** a developer opens the lab
- **THEN** it says tools will be added here

### Requirement: AI usage
A page SHALL show the AI's calls and estimated cost by day, by class and by kind of call.

#### Scenario: One week
- **WHEN** a developer opens the usage page
- **THEN** it shows each day's calls and cost, with totals per class and per kind
