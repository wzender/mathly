## ADDED Requirements

### Requirement: Sending a suggestion
Everyone signed in SHALL have "💡" (הצעה או משוב) in the header. It SHALL open a sheet with the kind (💡 רעיון, 🐞 משהו לא עובד, 💬 אחר) and the text (1 to 2,000 characters), and send it with the screen the person was on. A person SHALL send at most 20 a day.

#### Scenario: A student reports a problem
- **WHEN** a student opens "💡", picks "משהו לא עובד", writes and sends
- **THEN** the sheet thanks them and the suggestion is kept with their email, roles and screen

### Requirement: Reading suggestions
Only the developer SHALL read the suggestions: a card on the developer's screen with the open ones first (who, when, from which screen) and a button that marks one handled or opens it again.

#### Scenario: Handled
- **WHEN** the developer marks a suggestion handled
- **THEN** it moves under "טופלו"
