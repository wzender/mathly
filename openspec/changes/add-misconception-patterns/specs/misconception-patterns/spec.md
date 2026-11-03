# Spec Delta

## Purpose

Remembers which named misconceptions a student's wrong answers show, across all multiple-choice practice, and shows the student the misconceptions that keep coming back across skills, with what to practise, so they work on the cause and not only on one skill.

## ADDED Requirements

### Requirement: Every tagged wrong answer is recorded
The system SHALL record each wrong multiple-choice answer whose choice names a misconception, with the misconception, the skill, the question, the time and the activity (skill practice, mixed review or practice exam). Practice-exam answers SHALL be recorded once, when the exam is handed in. Recording SHALL NOT change the feedback, scoring, mastery or review of the answer.

#### Scenario: A wrong answer in skill practice is recorded
- **WHEN** a student picks a wrong choice tagged `sign_mid` in skill `t_ext`
- **THEN** the student's progress holds one record with misconception `sign_mid`, skill `t_ext`, that question, the time and activity "practice"

#### Scenario: A wrong answer in mixed review is recorded
- **WHEN** a student picks a wrong choice in a mixed review
- **THEN** a record with activity "review" is added, and the skill's next review is scheduled exactly as before

#### Scenario: A practice exam is recorded when handed in
- **WHEN** a student changes a wrong pick before handing in a practice exam, then hands it in with two wrong answers
- **THEN** exactly two records with activity "exam" are added, for the final picks only

#### Scenario: A left practice exam records nothing
- **WHEN** a student leaves a practice exam without handing it in
- **THEN** no records are added

#### Scenario: A right answer records nothing
- **WHEN** a student picks the right choice
- **THEN** no record is added

### Requirement: The mistake log stays on the device and is bounded
The mistake log SHALL be kept with the rest of the student's progress on the device, per account, and SHALL keep only the newest 500 records. Progress saved before this change SHALL load and work with an empty log.

#### Scenario: Old progress without a log
- **WHEN** a student whose saved progress has no mistake log opens the math path
- **THEN** the path works as before and the first wrong answer starts the log

#### Scenario: The log is capped
- **WHEN** a 501st record is added
- **THEN** the oldest record is dropped and 500 remain

### Requirement: Recurring misconceptions are identified
A misconception SHALL count as recurring when it was recorded at least twice in the last 30 days and at least once in the last 14 days. Recurring misconceptions SHALL be ordered by how many different skills they appeared in, then by count, then by most recent, and at most three SHALL be shown.

#### Scenario: Two occurrences make a pattern
- **WHEN** `sign_mid` was recorded twice in the last 30 days, once of them in the last 14 days, and `ext_partial` once
- **THEN** `sign_mid` is a recurring misconception and `ext_partial` is not

#### Scenario: Spread across skills comes first
- **WHEN** `sign_mid` was recorded 3 times in 3 different skills and `move_sign` 4 times in 1 skill
- **THEN** `sign_mid` is listed before `move_sign`

#### Scenario: Old records do not count
- **WHEN** a misconception's only records are older than 30 days
- **THEN** it is not a recurring misconception

### Requirement: The home screen shows a patterns card
The math home screen SHALL show a "patterns that come back" card when there is at least one recurring misconception, naming the top one and in how many skills it appeared. Without recurring or stopped patterns the card SHALL NOT be shown. The card's words SHALL describe the mistake, not the student.

#### Scenario: Card appears
- **WHEN** a student has a recurring misconception
- **THEN** the home screen shows the card with that misconception's name and its number of skills

#### Scenario: No card without a pattern
- **WHEN** a student has no recurring misconception and no pattern that has stopped
- **THEN** no patterns card is shown

### Requirement: The patterns sheet says what to practise
Opening the card SHALL show each recurring misconception (at most three) with its name, its tip, how many times and in how many skills it came up in the last 30 days, and when it last came up. Each SHALL offer a button to practise the skill to strengthen: the misconception's own back-skill when it names one, otherwise the skill where it came up most. Each button SHALL open that skill's practice.

#### Scenario: A misconception with a back-skill
- **WHEN** the recurring misconception `ext_partial` names `t_ext` as its back-skill
- **THEN** its entry offers a button that opens practice of `t_ext`

#### Scenario: A misconception without a back-skill
- **WHEN** the recurring misconception `sign_mid` has no back-skill and came up most in `t_simplify`
- **THEN** its entry offers a button that opens practice of `t_simplify`

### Requirement: Improvement is shown
The patterns sheet SHALL list, separately and at most three, misconceptions that were recorded at least twice within some 30-day span, last recorded between 14 and 60 days ago, as patterns that have stopped. When no misconception is recurring but one has stopped, the card SHALL be shown and say so.

#### Scenario: A pattern stops
- **WHEN** `sign_mid` was recorded 3 times 20 days ago and not since
- **THEN** the sheet lists `sign_mid` among the patterns that have stopped, and not among the recurring ones

#### Scenario: A long-stopped pattern is no longer listed
- **WHEN** a misconception was last recorded more than 60 days ago
- **THEN** it is listed neither as recurring nor as stopped

### Requirement: The path marks the skills to strengthen
On the math path, every skill that a recurring misconception names as its skill to practise SHALL be marked as a skill to strengthen ("לחזק") on its star, so a student following the path meets it there. The "continue here" mark of the next skill SHALL take precedence over this tag.

#### Scenario: A finished skill to strengthen is marked
- **WHEN** `ext_partial` is recurring, names `t_ext` as its back-skill, and `t_ext` is finished
- **THEN** the star of `t_ext` on the path is marked and tagged "לחזק"

#### Scenario: No pattern, no mark
- **WHEN** the student has no recurring misconception
- **THEN** no star on the path is marked to strengthen

### Requirement: A recurring mistake is named where it happens
When a wrong answer in skill practice or mixed review shows a misconception that is recurring (counting this answer), its feedback SHALL add a short note saying how many times and in how many skills it came up in the last 30 days, with a button to practise its skill to strengthen unless that skill is already offered in the same feedback.

#### Scenario: The second time the same mistake comes up
- **WHEN** `ext_partial` was recorded once in `t_ext_eq` and the student now picks an `ext_partial` choice in `t_simplify`
- **THEN** the feedback says it came up 2 times in 2 skills and offers practice of `t_ext` once

#### Scenario: A first mistake has no note
- **WHEN** a misconception is recorded for the first time
- **THEN** the feedback shows no pattern note
