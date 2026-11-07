# PRD: Mathly – Skill Mastery and Test Readiness

## 1. Introduction / Overview

Mathly is a math practice app for middle- and high-school students and their teachers.
Students often finish a topic without really mastering it, and then arrive at the school test unprepared:
they never practiced mixing topics, never worked under time pressure, and don't know where their gaps are.

Mathly solves this with two tools:

1. **The path** – a self-paced route through every skill, built on proven learning methods
   (worked examples, gradual removal of help, immediate feedback, mastery over several days).
2. **The test countdown** – once the teacher sets a test, the app plans the student's last weeks before it:
   finish the path, take two exercise tests, take one simulation test, and review what failed.

Teachers give and check assignments, set tests, and see the class's progress per skill and per lesson.

**The app is written from scratch.** Only two parts of the current app are kept (see 7.1):
the **exercise bank** and the **drawing board**. Everything else – screens, server, database, sign-in – is new.

### Glossary

| Term | Hebrew | Meaning |
|---|---|---|
| skill | מיומנות | A specific topic, e.g. פירוק טרינום |
| exercise | תרגיל | A question on a certain topic. Can be either open-ended or multiple choice |
| lesson | שיעור | A set of skills, e.g. טכניקה אלגברית 1 |
| quiz | בוחן | A test on a single lesson. Can be retaken; best grade wins; each retake draws new questions. It is the only quiz type (no one-time summary quiz); its best grade is the lesson's grade |
| exercise test | מבחן תרגול | A timed test on a set of lessons. Can be retaken; best grade wins |
| simulation test | מבחן סימולציה | A timed test on a set of lessons. One time only |
| test | מבחן | The real-life test. Appears in the app as a date + the lessons it covers + number of questions and time limit (default 12 questions, 90 minutes). Set by the teacher |

## 2. Goals

1. Help every student **master each skill**: mastery is proven, not assumed (3 correct in a row, no hints, on 2 different days).
2. Help every student **get ready for the real test**: on the test day, the student has mastered the covered skills,
   practiced mixed and timed questions, and taken one full simulation.
3. Give the teacher a clear, per-student picture of **which skills and lessons** each student has covered.

## 3. User Stories

**Student**
- As a student, I want to see a solved example and understand *why* each step is done, so I can solve the next one myself.
- As a student, I want the help to fade gradually, so I learn to solve alone without being thrown in at the deep end.
- As a student, when I get something wrong, I want to know *what* my mistake was and get a similar question, so I really learn it and don't just memorize the answer.
- As a student, I want to open any lesson at any time, so I can follow what my class is learning.
- As a student, I want to see how many days are left until my test, how ready I am, and what to do today, so I don't have to plan by myself.
- As a student, I want to practice with timed, mixed tests before the real test, so the real test doesn't surprise me.
- As a student, I want one full simulation of the real test, so I know where I stand while there is still time to fix gaps.
- As a student, I want to solve on a drawing board when a question needs a full solution, and hand it in from there.

**Teacher**
- As a teacher, I want to give an assignment from a file, from a photo, or by writing it on the drawing board, so I can use whatever material I already have.
- As a teacher, I want to check submitted assignments and give a grade and feedback.
- As a teacher, I want to set a test date and the lessons it covers, so the app prepares my students for it.
- As a teacher, I want to see who has taken the simulation test.
- As a teacher, I want a heat map of skills per student, so I can see at a glance which skills the class struggles with.
- As a teacher, I want to see how much of each lesson each student has covered.

## 4. Functional Requirements

### 4.1 Skill learning (the path)

Each skill takes the student through four stages, in this order.

1. **Worked example.** The system must show a fully solved example of the skill, one step at a time.
   After each step, the system must ask the student "why this step?" (multiple choice) before revealing the next one.
2. **Faded examples.** The system must show solved examples with steps removed: first one step missing, then two, and so on.
   The student must fill in each missing step. A wrong step gets immediate feedback (see requirement 4).
3. **Practice.** The system must give the student practice questions on the skill, taken from the exercise bank.
4. **Feedback on mistakes.** After a wrong answer, the system must:
   - show feedback that names the specific mistake, using the mistake attached to the chosen wrong answer in the exercise bank
     (its name and tip, e.g. "טעות סימן באיבר האמצעי");
   - not reveal the correct answer;
   - give the student a **similar** question (same skill, a different question), not the same question again.
5. **Mastery.** A skill must become **mastered** when the student answers 3 questions correctly in a row,
   on the first try, without opening help or the worked example, and these answers are spread over at least 2 different calendar days.
6. **Skill states.** Every skill, for every student, must be in one of these states:
   - **not started** – no answers yet;
   - **learning** – at least one answer, not yet mastered;
   - **mastered** – met the rule in requirement 5.
   A mastered skill stays mastered. It must **not** fade or decay over time.
7. **All lessons open.** The student must be able to open any lesson, and any skill inside it, at any time, in any order.
8. **Daily goal and streak.** 5 correct answers per day builds a streak.
9. **Collection.** The student must have a collection screen that shows what they achieved: each mastered skill and each completed lesson.

### 4.2 Quizzes (בוחן)

10. **Quiz per lesson.** Each lesson must have a quiz. The student can retake it; the best grade counts; every retake draws new questions.
    The quiz's best grade is the lesson's grade.
11. **After a quiz,** the system must list the skills where the student lost points, so they can practice them before retaking.

### 4.3 Test countdown

12. **Setting a test.** The teacher must be able to set a test: date + the lessons it covers (+ an optional note),
    plus the real test's **number of questions** and **time limit**. These start with defaults
    (12 questions, 90 minutes) that the teacher can change.
13. **The countdown plan.** From the moment a test is set, the system must show the student a plan that depends on the days left:

    | Days before the test | What the app asks the student to do |
    |---|---|
    | until 9 | Finish the path for every covered lesson (bring every covered skill to "mastered") |
    | ~9 | Exercise test 1 |
    | ~7 | Exercise test 2 |
    | ~5 | Simulation test (required) |
    | 4 → 1 | Review the skills that failed in the simulation; light mixed review the day before |

    The day numbers are **recommendations**: the student can start each step earlier or later.
    If the test is set less than 9 days ahead, the system must keep the same order and shorten the gaps evenly.
14. **Home screen reminder.** The home screen must show, for the nearest test:
    days left, the readiness meter (see 4.6), and **one task for today** taken from the plan.
    When several tests are coming up, "today's task" comes from the **closest** one.

### 4.4 Exercise tests (מבחן תרגול)

15. **Created by the app.** When the teacher sets a test, the system must create 2 exercise tests for every student in the class and place them on the student's countdown.
16. **Teacher can assign one.** The teacher must be able to send an exercise test to the whole class as an assignment.
17. **Retakes.** The student can start or retake an exercise test at any time. Each retake draws new questions; the best grade counts.
18. **Like the simulation.** Exercise tests must have the same number of questions and the same time limit as the simulation
    (that is, as the real test, requirement 12), mix questions from all covered lessons, and not show the skill name.
    Feedback comes **only at the end**, not after each question.
19. **Question mix.** The system must pick questions in these proportions:

    | Exercise test | Weak skills | Other covered skills |
    |---|---|---|
    | 1 | 60% | 40% |
    | 2 | 30% | 70% |

    "Weak skill" = a skill in the "learning" state, or one the student answered wrong in a previous exercise test.
    Skills in the "not started" state must not appear; instead, the card must list them as "practice these first".
    If the student has fewer weak skills than needed, fill the rest from the other covered skills.
20. **Result links back.** After an exercise test, the system must show the weak skills it found and link each one to its place in the path.

### 4.5 Simulation test (מבחן סימולציה)

21. **Required, one attempt.** Every student must take one simulation test per real test. It can be taken only once.
22. **Like the real test.** The simulation must cover all the lessons of the real test, with the number of questions and the time limit the teacher set for the real test (requirement 12),
    no skill names, and no feedback until the end.
23. **Window.** The simulation becomes available ~5 days before the test and stays available until the test day.
    It must be shown as **required** on the student's home screen until it is taken.
24. **After the simulation,** the system must list the skills that failed and turn them into the review tasks of the last days (requirement 13).

### 4.6 Readiness meter

25. **Readiness meter.** For each upcoming test, the system must show the student (and the teacher) a readiness meter made of:
    - % of the covered skills that are mastered;
    - the best grade of each exercise test;
    - the simulation test grade (once taken).

### 4.7 Student screens

26. **Home:** my assignments (המשימות שלי) from the teacher; the upcoming-test reminder (requirement 14); continue the path.
27. **Path:** all lessons and skills, each skill showing its state.
28. **Grades:** all quiz (best grade), exercise test, simulation and assignment grades.
29. **Collection:** see requirement 9.
30. **Drawing board.** Wherever a question needs a written solution (open questions, assignments), the student must be able to
    solve on the drawing board and hand in the board as their answer.

### 4.8 Teacher screens

31. **Give an assignment.** The teacher must be able to create an assignment (title, note, due date) and load its content from:
    - the computer (file upload: PDF or images);
    - a photo taken with the device camera;
    - the drawing board: the teacher writes or draws the assignment on the board, and it is saved as the assignment's page(s).
32. **Check assignments.** The teacher must be able to open each student's submission, give a grade (0–100) and a note, or send it back for correction.
33. **Tests tab.** The teacher must be able to set a test (requirement 12) and see, for each test, which students have taken the simulation test and which have not.
34. **Class heat map.**
    - Rows: students. Columns: skills (grouped by lesson).
    - Each cell is colored by the skill state: not started / learning / mastered.
    - Tabs for the period: **Sep–Dec** and **Jan–Jun**. A period shows the skills of the lessons taught in it, and states as they were at the end of the period (or today, for the current period).
35. **Student lesson coverage.**
    - Rows: students. Columns: lessons.
    - Each cell shows the % of the lesson's skills the student has mastered, and the student's best quiz (בוחן) grade for that lesson.
    - Same period tabs: **Sep–Dec** and **Jan–Jun**.

## 5. Non-Goals (Out of Scope)

- Reusing any part of the current app other than the exercise bank and the drawing board.
- Skills do not decay or need re-mastering over time.
- Lessons are never locked; the app does not force an order.
- There is no one-time summary quiz (בוחן מסכם).
- The app does not grade the real school test or import its grades.
- The app does not replace the teacher's lesson plan or teach new material in class.
- No student-to-student features (chat, leaderboards).

## 6. Design Considerations

- Hebrew, right-to-left. Works on phones first; the teacher views (heat map, coverage) must also work well on a computer.
- Math is written in LaTeX inside `$…$` in the exercise bank; the app must render it.
- Mastered skills must look clearly different from "learning" and "not started" ones.
- Heat map colors must be readable in light and dark mode and must not rely on color alone (add a symbol or text in each cell).
- The "one task for today" on home must be a single, obvious button.

## 7. Technical Considerations

### 7.1 What is kept from the current app

**Exercise bank** – `app/math_algebra9.json` (9th grade algebra/geometry):
- `units`: 24 lessons (id, name, month, and for 4 of them a `quiz` with open questions, points, minutes and the skills each question tests).
- `skills`: 96 skills (id, lesson, name, short name, description, prerequisites, month, `questions`).
- `questions`: 1,050 multiple-choice questions. Each wrong choice has a `mistake` id.
- `mistakes`: 244 mistakes, each with a name, a tip, and the skill to go back to (`back`).

**Drawing board** – `static/math-board.js` (the board), `static/board-math.js` (typed math on the board) and
`static/vendor/mathlive/` (the math keyboard library, MIT license, loaded by board-math.js).
It exposes `window.MathlyBoard` and turns a sketch into a picture for handing in.

### 7.2 Notes for the new build

- **Content gaps in the bank.** The new app needs content the bank does not have yet:
  - worked examples and faded examples (requirements 1–2): no skill has one today;
  - "why this step?" choices for each step of a worked example;
  - quizzes for 20 of the 24 lessons (requirement 10);
  - one skill has no questions;
  - enough questions per skill for "similar question" (requirement 4) and for retakes that draw new questions.
  `scripts/draft_examples.py` from the current app drafts worked examples with AI for a teacher to approve; it may be reused as a tool.
- Grades that matter (quiz, exercise test, simulation) must be computed and stored on the server, so a student cannot change them from the device.
- Mastery (requirement 5) needs the date of each answer, so the server can check the "2 different days" rule.
- The simulation's timer must be kept on the server, so refreshing or closing the app does not reset it.
- Open questions in quizzes and assignments need checking: by the teacher (requirement 32), possibly with AI help (see Open Questions).

## 8. Success Metrics

- ≥ 90% of students take the simulation test before each real test.
- On test day, students have mastered on average ≥ 80% of the covered skills.
- ≥ 75% of students take both exercise tests before each real test.
- Teachers open the heat map or the coverage view at least once a week.

## 9. Open Questions

1. **Default time limit:** 90 minutes was chosen as the default for a real test. Is that right for most tests, or should it be 45?
2. **Existing data:** should students, classes and progress from the current app move to the new one, or does the new app start empty?
3. **Sign-in and roles:** keep sign-in with the school's Google accounts? Is there an admin role (creates classes, adds students), or does the teacher do that?
4. **Subjects:** math only, or also science (the current app has a small science part)?
5. **Checking open answers:** does the teacher check everything by hand, or should AI suggest a grade for the teacher to approve?
6. **Tech stack and location:** same repository (new folder) or a new one? Any preferred stack, or keep Python + Supabase?
