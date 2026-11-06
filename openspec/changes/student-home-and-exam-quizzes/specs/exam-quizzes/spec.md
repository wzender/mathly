# Spec Delta

## Purpose

Gives each student quizzes chosen for them before an exam: two strengthening quizzes aimed at a comfortable success rate, then a quiz like the exam, with fresh questions on every retake and the best grade counting.

## ADDED Requirements

### Requirement: Three quizzes before an exam
When the student's next exam names units and is 7 days away or less, home SHALL offer three quizzes for it: "בוחן חיזוק 1", "בוחן חיזוק 2" and "בוחן כמו במבחן". Each SHALL have 12 multiple-choice questions taken from the topics of the exam's units.

#### Scenario: Exam in 6 days
- **WHEN** the math exam naming units `t`, `t2`, `k`, `l`, `o` is in 6 days
- **THEN** home shows the three quizzes, each with 12 questions from those units only

#### Scenario: Exam in 10 days
- **WHEN** the next exam is 10 days away
- **THEN** home does not show the three exam quizzes

### Requirement: Two quizzes without an exam
When no exam naming units is 7 days away or less, home SHALL offer the two strengthening quizzes over the units taught so far by the class schedule, and no exam-like quiz.

#### Scenario: Quiet week
- **WHEN** the class has no exam in the next 7 days and it is November
- **THEN** home shows "בוחן חיזוק 1" and "בוחן חיזוק 2" over the units scheduled up to November

### Requirement: Strengthening quizzes aim at a set success rate
Each topic SHALL have an estimated chance that the student answers it right, from their answers so far. Quiz 1 SHALL choose topics so the expected score is about 70%, quiz 2 about 80%. Both SHALL prefer topics the student has started but not mastered, and fill the rest with topics they finished.

#### Scenario: Mostly near-mastered topics
- **WHEN** a student has 4 started-but-unfinished topics and 8 finished topics in the exam's units
- **THEN** quiz 1 draws most of its questions from the 4 started topics, and its expected score is between 65% and 75%

#### Scenario: Easier second quiz
- **WHEN** the same student opens quiz 2
- **THEN** it has more questions from finished topics than quiz 1, and its expected score is between 75% and 85%

### Requirement: Topics not started are not quizzed
A topic the student has never practised MUST NOT appear in any of the three quizzes. If fewer than 6 questions remain, the quiz SHALL NOT start; it SHALL list the topics to learn first, each opening that topic. With 6 to 11, it SHALL be shorter.

#### Scenario: Not started yet
- **WHEN** the student never opened the median-to-hypotenuse topics of unit `o`
- **THEN** none of the quizzes asks about them, and the preparation plan lists them as topics to learn

#### Scenario: Too little practised
- **WHEN** only 4 questions can be drawn from the topics the student started
- **THEN** the quiz cannot be started, and it shows the topics to learn first

### Requirement: Little data falls back to recent topics
A topic with fewer than 5 answers SHALL NOT be treated as known or as needing work. When a strengthening quiz cannot reach 12 questions from topics with enough answers, it SHALL fill the rest from the most recently taught topics the student has started.

#### Scenario: New student
- **WHEN** a student has 2 answers in each of their started topics
- **THEN** quiz 1 is drawn from the most recently taught started topics, not ranked by their answers

### Requirement: Strengthening quizzes give feedback right away
In both strengthening quizzes, the student SHALL see after each answer whether it was right, and the tip of a wrong answer's mistake. After a wrong answer, the topic's worked example SHALL be offered before moving on.

#### Scenario: Wrong answer
- **WHEN** a student picks a wrong choice tagged with a mistake in quiz 1
- **THEN** the choice is marked wrong, the right one is shown, the mistake's tip appears and "לראות דוגמה פתורה" is offered

### Requirement: Exam-like quiz gives feedback at the end
The exam-like quiz SHALL hide topic names, mix questions from all the exam's units, and give no feedback until it is handed in. The result SHALL show the score, the score per unit and at most 3 things to fix, each linking to its topic.

#### Scenario: Handing in
- **WHEN** a student hands in the exam-like quiz with mistakes of 5 different kinds
- **THEN** the result shows the score, the score per unit and the 3 most frequent mistakes, each with a button to practise its topic

### Requirement: Confidence and reflection in the exam-like quiz
Each question of the exam-like quiz SHALL offer an optional "how sure are you?" with three levels. The result SHALL list answers marked sure that were wrong, and offer an optional one-line reflection (up to 140 characters) kept with the result. Neither SHALL be required to hand in.

#### Scenario: Sure but wrong
- **WHEN** a student marked 2 answers "בטוח/ה" and both were wrong
- **THEN** the result lists those 2 questions under "הייתי בטוח/ה וטעיתי"

#### Scenario: Skipping both
- **WHEN** a student answers without marking confidence and leaves the reflection empty
- **THEN** the quiz is handed in and scored as usual

### Requirement: Retakes draw new questions
Each quiz SHALL be retakeable any number of times. A retake SHALL NOT repeat questions the student saw in that quiz's earlier attempts for the same exam, while unseen questions remain for the chosen topics. When none remain, the questions seen longest ago SHALL be used first.

#### Scenario: Second attempt
- **WHEN** a student retakes quiz 1 for the November exam
- **THEN** none of its 12 questions appeared in their first attempt of quiz 1

### Requirement: The best grade counts
Each quiz SHALL show the student's best grade and how the latest attempt compares with their previous one. Results MUST NOT be compared with other students.

#### Scenario: Improvement
- **WHEN** a student got 7 of 12, then 10 of 12 in quiz 1
- **THEN** quiz 1 shows "הכי טוב: 10/12" and "+3 מהפעם הקודמת"

#### Scenario: Lower retake
- **WHEN** the student then gets 8 of 12
- **THEN** quiz 1 still shows "הכי טוב: 10/12"

### Requirement: Recommended day for each quiz
Each quiz SHALL show its recommended days: quiz 1 from 7 to 4 days before the exam, quiz 2 from 5 to 3, the exam-like quiz from 3 to 2. Home SHALL mark the quizzes recommended for today. All three SHALL be available from 7 days before the exam until the exam day.

#### Scenario: Three days before
- **WHEN** the exam is in 3 days
- **THEN** quiz 2 and the exam-like quiz are marked "מומלץ להיום", and quiz 1 can still be started

### Requirement: No weakness wording
Quiz names, descriptions and results MUST NOT call topics or students weak. Topics to work on SHALL be named as topics to strengthen or practise.

#### Scenario: Result wording
- **WHEN** a quiz result lists topics with lost points
- **THEN** they are introduced as "כדאי לחזק", never with the word "חולשה" or "חלש"

### Requirement: Quizzes complete the preparation plan
The exam preparation plan's final step SHALL be the three quizzes instead of one practice exam. Each SHALL be checked off when the student hands in an attempt after the plan was opened.

#### Scenario: Plan steps
- **WHEN** the student opens the plan of the November exam
- **THEN** its last three steps are "בוחן חיזוק 1", "בוחן חיזוק 2" and "בוחן כמו במבחן"

#### Scenario: Step done
- **WHEN** the student hands in quiz 1 after opening the plan
- **THEN** that step is shown as done
