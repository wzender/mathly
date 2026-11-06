# Spec Delta

## Purpose

Shows the class teacher, for each student and for the class, the skills and misconceptions that most need work, with the evidence behind each one, so the teacher knows whom to help with what.

## ADDED Requirements

### Requirement: Unit-quiz questions name their skills
Each unit-quiz question SHALL name one to three skills of its unit that it tests. Loading the content data MUST fail when a quiz question names no skill or a skill outside its unit.

#### Scenario: Valid tags
- **WHEN** question 2 of unit `t`'s quiz names `t_ext_eq`
- **THEN** the content loads and the question carries that skill

#### Scenario: Skill of another unit
- **WHEN** a quiz question of unit `t` names `g_pyth`
- **THEN** loading fails, naming the unit and the question

### Requirement: Quiz points lost are counted per skill
For each student, the system SHALL count, per skill, the points lost in their checked final and practice quiz answers, splitting a question's lost points equally among its skills, over the last 60 days.

#### Scenario: Lost points on a tagged question
- **WHEN** a student got 10 of 25 points on a question tagged `t_ext` and `t_ext_eq`
- **THEN** each of the two skills counts 7.5 lost points for that student

#### Scenario: Unchecked answers are not counted
- **WHEN** an answer has no completed check
- **THEN** it adds no lost points

### Requirement: Teacher sees a student's focus areas
Each student's card in the class report SHALL open with a "על מה לעבוד" section listing at most 5 skills, ranked by a weakness score that combines: quiz points lost on the skill, wrong answers in the skill in the last 14 days, being started but not finished, and being fading. Each listed skill SHALL state its evidence in words.

#### Scenario: Evidence in words
- **WHEN** `g_pyth` is a student's top focus skill
- **THEN** it is listed with its evidence, for example "4 טעויות ב־14 ימים · איבד 12 נק׳ בבוחן הסופי · לא הושלם"

#### Scenario: No weak skill
- **WHEN** a student has no skill with a weakness score above zero
- **THEN** the section says there is no focus area right now

### Requirement: Focus areas include recurring misconceptions
The "על מה לעבוד" section SHALL also list the student's recurring misconceptions, with the number of times and skills, and their skill to strengthen, the same as the student's own patterns sheet. The words SHALL describe the mistake, not the student.

#### Scenario: Recurring misconception
- **WHEN** a student has `sign_mid` recurring in 3 skills
- **THEN** the card lists "טעות סימן באמצע הביטוי · 3 פעמים ב־3 מיומנויות" with its skill to strengthen

### Requirement: Sources are labelled
Each piece of evidence SHALL be labelled by its source: checked by the server (quiz answers and teacher reviews) or reported by the student's device (practice answers, misconceptions, fading).

#### Scenario: Mixed sources
- **WHEN** a focus skill has quiz points lost and wrong practice answers
- **THEN** the quiz evidence has no device label and the practice evidence carries the device label

### Requirement: Teacher sees class-wide focus areas
The report SHALL show for the class the 5 skills with the most students listing them among their focus skills, and the 3 misconceptions recurring in the most students, each with the number of students and a way to open the list of those students.

#### Scenario: Shared weakness
- **WHEN** 11 students list `g_pyth` among their focus skills
- **THEN** the class view shows `g_pyth` with "11 תלמידים", and opening it lists the 11 students

### Requirement: Focus area leads to action
Each focus skill, for a student or for the class, SHALL offer to assign it as focus practice to that student, or to the students who list it.

#### Scenario: Assign from the class view
- **WHEN** the teacher presses "לתת תרגול" on `g_pyth` in the class view
- **THEN** the focus-practice form opens with `g_pyth` and the 11 students already chosen
