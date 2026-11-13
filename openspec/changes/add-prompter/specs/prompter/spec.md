# Spec Delta

## Purpose

A teleprompter for the texts developers record: saved texts on every device, a full-screen scrolling view, and an AI-written outline on request.

## ADDED Requirements

### Requirement: Developers only
The prompter's routes and card SHALL be reachable only by developers.

#### Scenario: Manager
- **WHEN** a manager asks for the prompter's texts
- **THEN** it is refused with 403

### Requirement: Prompter texts
A developer SHALL save texts that belong to their account and appear on every device: a title up to 120 characters (the text's first line when left empty), a text up to 100,000 characters, and at most 200 texts. The list SHALL show the last changed first. The text being edited SHALL also be kept in the browser until it is saved.

#### Scenario: Another device
- **WHEN** a developer saves a text on a computer and opens the prompter on a tablet
- **THEN** the text is there

#### Scenario: Not yet saved
- **WHEN** a developer types a text and reloads the page before saving
- **THEN** the typed text is back and the card says it is not saved yet

#### Scenario: Too many
- **WHEN** a developer with 200 texts saves another
- **THEN** it is refused and says the limit

### Requirement: Prompter screen
The prompter SHALL show a text full screen and scroll it. Space starts and stops, ↑/↓ change speed, +/− change size, M mirrors, F is full screen and Esc leaves; the mouse and a presentation remote SHALL work too.

#### Scenario: Mirror
- **WHEN** a developer presses M during scrolling
- **THEN** the text is shown mirrored

### Requirement: Outline
On request the AI SHALL write a saved text's outline: the same slides with two to four very short topic reminders each. It SHALL be kept with the text, editable, and shown in the prompter on its own. The request SHALL carry only the text, and its usage SHALL be recorded as `prompter`. Changing the text without sending an outline SHALL drop the outline. When the AI fails, the card SHALL say why in Hebrew and keep the text.

#### Scenario: Text changed
- **WHEN** a developer edits a text that has an outline and saves only the text
- **THEN** the outline is removed

#### Scenario: AI busy
- **WHEN** the AI provider is overloaded
- **THEN** the card says so and the text is unchanged
