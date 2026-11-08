# Spec Delta

## MODIFIED Requirements

### Requirement: Hebrew, right-to-left, phone first
Every screen SHALL be in Hebrew, laid out right-to-left, and designed for phones first. The teacher, manager, admin and developer screens SHALL also work well on a computer.

#### Scenario: Opening on a phone
- **WHEN** a student opens the app on a phone
- **THEN** the screen is in Hebrew, right-to-left, and fits the phone's width

#### Scenario: Manager on a computer
- **WHEN** a manager opens the classes screen on a computer
- **THEN** the class list uses the wide screen and nothing is cut off

## ADDED Requirements

### Requirement: The sky look
Every screen SHALL follow one "sky" look: a dark-blue night with aurora and starlight accents, gold for mastery, and an owl mascot. The app SHALL always be dark, as mathly1 is; there is no light mode. The page background SHALL be a dark night with two soft glows and small fixed stars.

#### Scenario: A light device
- **WHEN** the device asks for light mode
- **THEN** every screen is still dark, with readable text

#### Scenario: The sky behind the page
- **WHEN** any screen is open
- **THEN** the page background is dark, with two soft glows (blue at the top right, purple at the left) and small stars, all fixed while the page scrolls, and nothing in the background moves

### Requirement: Readable without color or motion
State and result SHALL never be shown by color alone: every state has a symbol or a word. Touch targets SHALL be at least 44px. Animations SHALL stop when the device asks for reduced motion.

#### Scenario: Reduced motion
- **WHEN** the device asks for reduced motion
- **THEN** no element of the app animates

### Requirement: Server time and decisions
The server SHALL decide the date of every event by its own clock and the calendar day in Israel, never the device's. Correctness of answers, mastery, grades, budgets and timers SHALL be decided and stored on the server.

#### Scenario: Device clock changed
- **WHEN** a student sets the device's date to tomorrow and answers a question
- **THEN** the answer is dated by the server's today

### Requirement: mathly1 stays available
The app SHALL only add its own tables (named with an `m2_` prefix) and MUST NOT change, empty or delete any table, policy or storage bucket that mathly1 uses, so the Hugging Face Space can be switched back to mathly1 with its data as it was.

#### Scenario: Switching back
- **WHEN** the Space is switched back to mathly1 after mathly2 has run
- **THEN** mathly1's students find their data as they left it

### Requirement: Safe settings
The server SHALL refuse to start when only some of the Supabase settings are given. With none given it SHALL run for local development with an in-memory store and a sign-in, marked "dev only", that accepts an email address.

#### Scenario: Half-configured
- **WHEN** the server starts with a Supabase URL but no secret key
- **THEN** it does not start and says which settings are missing

### Requirement: Where settings come from
The server SHALL read its settings from real environment variables first, then from the app's own `.env` file if it has one, then from the repository's `.env` file shared with mathly1. A setting found in an earlier source SHALL win over the same setting in a later one.

#### Scenario: Shared file
- **WHEN** the app has no `.env` of its own and the repository's `.env` holds the Supabase settings
- **THEN** the app uses those settings

#### Scenario: A real variable wins
- **WHEN** the teacher list is set in the environment and in a file
- **THEN** the environment's list is used

### Requirement: Database problems are explained
When the database cannot be reached, or refuses a request that is not a conflict the person caused, the person SHALL see a message saying the database did not answer or refused, with a hint that the migrations may be missing, and the reason SHALL be written to the server log. The app MUST NOT report such a failure as a different problem, such as a name already in use.

#### Scenario: Missing column
- **WHEN** a manager saves a class and the database refuses because a migration was not applied
- **THEN** the manager sees that the database refused the request, not that the class name is taken, and the server log names the refusal
