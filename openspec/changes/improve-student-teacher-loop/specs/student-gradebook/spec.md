# Spec Delta

## Purpose

Gives a student one page with every grade the server holds for them, what each one means, and what is still waiting for a check, so they never have to hunt through quizzes and assignment cards.

## ADDED Requirements

### Requirement: Student opens their grades page
A signed-in student SHALL have a "הציונים שלי" page, reachable from the home screen and from the task list, grouped by unit. It SHALL list: the official grade of each unit's final quiz, their practice-quiz grades (best and latest), and the scores of their checked worksheets. All grades on it SHALL come from the server.

#### Scenario: Grades by unit
- **WHEN** a student has a final grade of 62 in unit `g`, practice grades 70 and 85 in unit `g`, and a worksheet score of 90 in an assignment of unit `g`
- **THEN** the unit `g` section shows "בוחן סופי: 62", "תרגול: הכי טוב 85 · אחרון 85" and the worksheet with 90

#### Scenario: Edited device progress
- **WHEN** the student's device progress claims a different quiz score
- **THEN** the grades page shows the server's grade

### Requirement: Each grade is labelled by kind
Each grade SHALL say what it is: official final grade, practice grade, or worksheet score. Practice grades SHALL be marked as not counting toward the official grade.

#### Scenario: Practice label
- **WHEN** the page shows a practice-quiz grade
- **THEN** it carries the label "תרגול – לא נכנס לציון"

### Requirement: Waiting items are shown without a grade
Sittings and submissions that are handed in but not fully checked, or whose final results are not released, SHALL appear with their state and no grade.

#### Scenario: Unchecked answers
- **WHEN** a practice sitting has 1 of 4 answers still waiting for a check
- **THEN** it is listed as "ממתין לבדיקה · שאלה אחת" with no grade

#### Scenario: Final not released
- **WHEN** a final sitting is checked but the results are not released
- **THEN** it is listed as handed in, waiting for results, with no grade

### Requirement: Teacher comments are shown with the grade
When a grade has a teacher review or worksheet comment, the page SHALL show a marker for it, and SHALL list teacher comments the student has not opened yet at the top of the page.

#### Scenario: New comment
- **WHEN** the teacher commented on question 2 of a final sitting yesterday and the student has not opened it
- **THEN** the page shows it under "הערות חדשות מהמורה" with a link to that answer

### Requirement: Each grade opens its result
Each grade SHALL open the matching result: the quiz result screen with per-question points, feedback and solutions, or the checked worksheet with its pages, score and comment.

#### Scenario: Open a final result
- **WHEN** the student taps the final grade of unit `g`
- **THEN** the quiz result screen of that sitting opens

### Requirement: Grades stay private
A student SHALL see only their own grades. The grades request MUST NOT accept another student's id.

#### Scenario: Another student's grades
- **WHEN** a request for grades names a classmate's id
- **THEN** the server ignores the id and answers with the signed-in student's grades only
