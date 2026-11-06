# Spec Delta

## Purpose

Links each upcoming exam on the class exam board to the units it covers, and turns that into a readiness view and a preparation plan the student can follow one tap at a time.

## ADDED Requirements

### Requirement: Exams name the units they cover
An exam on a class's exam board SHALL be able to name the class units it covers, and an optional note of up to 300 characters (for example "פרק 3 עד עמוד 80"). Only the class teacher or a manager SHALL set them. Units outside the class's units MUST be rejected. Exams without units SHALL keep working as today.

#### Scenario: Teacher links units
- **WHEN** the teacher of 9א sets the math exam of 18/11 to cover units `t` and `g`
- **THEN** students of 9א see "חומר למבחן: ביטויים אלגבריים, משפט פיתגורס" on the exam

#### Scenario: Exam without units
- **WHEN** an exam names no units
- **THEN** it is shown with its subject and date only, and has no readiness view

### Requirement: Student sees an upcoming-exam view
For each upcoming exam that names units, the student SHALL be able to open a view with the days left, the units covered, the teacher's note and the student's readiness. The nearest such exam SHALL be linked from the home screen and from the task list.

#### Scenario: Open the nearest exam
- **WHEN** a student taps the countdown of the math exam in 5 days
- **THEN** the exam view opens with "עוד 5 ימים", the two units and the readiness

### Requirement: Readiness is shown per skill
The readiness of an exam SHALL list, for each skill of its units, the student's state (gold, finished, fading, practising, not started) using the same states as the path, and a summary of finished skills out of all skills. It SHALL also list the student's recurring misconceptions seen in those units, and their latest practice and official quiz grades of those units.

#### Scenario: Readiness summary
- **WHEN** units `t` and `g` have 14 skills and the student finished 9, 2 of them fading
- **THEN** the view shows "9 מתוך 14" and marks the 2 fading skills and the 5 not finished

#### Scenario: Misconception in an exam unit
- **WHEN** the student has the recurring misconception `sign_mid`, seen in skills of unit `t`
- **THEN** the view lists it with its tip and its skill to strengthen

### Requirement: Student gets a preparation plan
The exam view SHALL offer a plan in this order: skills not started or practising, then fading skills, then skills to strengthen from recurring misconceptions, then the units' practice quizzes, then a practice exam over the exam's units. Each step SHALL open with one tap and SHALL be checked off when done.

#### Scenario: Plan steps
- **WHEN** the student has 1 skill not started, 2 fading skills and no misconception
- **THEN** the plan lists the skill, then the 2 fading skills, then the practice quizzes of `t` and `g`, then "מבחן תרגול על החומר"

#### Scenario: Practice exam set to the exam's units
- **WHEN** the student opens the plan's practice exam step
- **THEN** a practice exam starts with units `t` and `g` chosen and no other unit

#### Scenario: Step done
- **WHEN** the student finishes a fading skill's review from the plan
- **THEN** that step is shown as done when they return to the exam view

### Requirement: Plan suggests a daily amount
When the exam is 2 or more days away, the plan SHALL suggest how many steps to do per day, so the remaining steps are spread over the days left, and SHALL show today's steps first.

#### Scenario: Six steps, three days
- **WHEN** 6 steps remain and the exam is in 3 days
- **THEN** the plan says "2 צעדים ביום" and shows the first 2 as today's

#### Scenario: Exam tomorrow
- **WHEN** the exam is tomorrow
- **THEN** the plan shows all remaining steps without a daily amount

### Requirement: Teacher sees class readiness for an exam
In the class report, the teacher SHALL see for each upcoming exam with units how many students finished each of its skills, and the students with the lowest readiness.

#### Scenario: Class readiness
- **WHEN** the teacher opens the 18/11 exam in the report
- **THEN** they see each skill of `t` and `g` with how many students finished it, and the 5 students with the fewest finished skills
