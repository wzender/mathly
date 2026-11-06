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

Much of the app already exists. Each requirement below is tagged:
- **[exists]** – already built; keep as is.
- **[change]** – already built, but must change to match this PRD.
- **[new]** – not built yet.

### Glossary

| Term | Hebrew | Meaning |
|---|---|---|
| skill | מיומנות | One specific topic, e.g. פירוק טרינום |
| exercise | תרגיל | One question on a skill. Open-ended or multiple choice |
| lesson | שיעור / יחידה | A set of skills, e.g. טכניקה אלגברית 1 |
| quiz | בוחן | A test on a single lesson. Can be retaken; best grade wins; each retake draws new questions |
| exercise test | מבחן תרגול | A timed test on several lessons. Can be retaken; best grade wins |
| simulation test | מבחן סימולציה | A timed test on several lessons, taken one time only, like the real test |
| test | מבחן | The real test at school. In the app it is a date + the lessons it covers, set by the teacher |
| weak skill | – | A skill in the "learning" state, or one the student failed in an exercise test |

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

**Teacher**
- As a teacher, I want to give an assignment from a file, from the classroom smart board, or from a photo, so I can use whatever material I already have.
- As a teacher, I want to check submitted assignments and give a grade and feedback.
- As a teacher, I want to set a test date and the lessons it covers, so the app prepares my students for it.
- As a teacher, I want to see who has taken the simulation test.
- As a teacher, I want a heat map of skills per student, so I can see at a glance which skills the class struggles with.
- As a teacher, I want to see how much of each lesson each student has covered.

## 4. Functional Requirements

### 4.1 Skill learning (the path)

Each skill takes the student through four stages, in this order.

1. **[change] Worked example.** The system must show a fully solved example of the skill, one step at a time.
   After each step, the system must ask the student "why this step?" (multiple choice or short answer) before revealing the next one.
   *Today the worked example exists inside the help window and shows the explanation of each step, but does not ask the student.*
2. **[new] Faded examples.** The system must show solved examples with steps removed: first one step missing, then two, and so on.
   The student must fill in each missing step. A wrong step gets immediate feedback (see 4).
3. **[change] Practice.** The system must give the student practice questions on the skill.
4. **[change] Feedback on mistakes.** After a wrong answer, the system must:
   - show feedback that names the specific mistake (e.g. "the sign changed when moving the term across"), not only "wrong";
   - not reveal the correct answer;
   - give the student a **similar** question (same skill, different numbers or wording), not the same question again.
   *Today the same question comes back after the others.*
5. **[change] Mastery.** A skill must become **mastered** when the student answers 3 questions correctly in a row,
   on the first try, without opening help or the worked example, and these answers are spread over at least 2 different calendar days.
   *Today a star turns gold after several correct first-try answers in a row, with no "2 days" rule.*
6. **[change] Skill states.** Every skill, for every student, must be in one of these states:
   - **not started** – no answers yet;
   - **learning** – at least one answer, not yet mastered;
   - **mastered** – met the rule in requirement 5.
   A mastered skill stays mastered. It must **not** fade or decay over time.
   *Today a star fades after two weeks without practice. Remove the fading, and remove the "mixed review" that is triggered by it.*
7. **[exists] All lessons open.** The student must be able to open any lesson, and any skill inside it, at any time, in any order.
8. **[exists] Daily goal and streak.** 5 correct answers per day builds a streak.
9. **[exists] Collection.** Each skill is a star; each completed lesson draws a constellation. The collection tab shows them.

### 4.2 Quizzes (בוחן)

10. **[exists] Quiz per lesson.** Each lesson has a quiz. The student can retake it; the best grade counts; every retake draws new questions.
11. **[exists] After a quiz,** the system must list the skills where the student lost points, so they can practice them before retaking.

### 4.3 Test countdown

12. **[exists] Setting a test.** The teacher must be able to set a test: date + the lessons it covers (+ an optional note).
13. **[change] The countdown plan.** From the moment a test is set, the system must show the student a plan that depends on the days left:

    | Days before the test | What the app asks the student to do |
    |---|---|
    | until 9 | Finish the path for every covered lesson (bring every covered skill to "mastered") |
    | ~9 | Exercise test 1 |
    | ~7 | Exercise test 2 |
    | ~5 | Simulation test (required) |
    | 4 → 1 | Review the skills that failed in the simulation; light mixed review the day before |

    The day numbers are **recommendations**: the student can start each step earlier or later.
    If the test is set less than 9 days ahead, the system must keep the same order and shorten the gaps evenly.
14. **[change] Home screen reminder.** The home screen must show, for the nearest test:
    days left, the readiness meter (see 4.6), and **one task for today** taken from the plan.

### 4.4 Exercise tests (מבחן תרגול)

15. **[change] Created by the app.** When the teacher sets a test, the system must create 2 exercise tests for every student in the class and place them on the student's countdown.
16. **[change] Teacher can assign one.** The teacher must be able to send an exercise test to the whole class as an assignment.
    *Today only admins can assign exercise tests to a class.*
17. **[exists] Retakes.** The student can start or retake an exercise test at any time. Each retake draws new questions; the best grade counts.
18. **[change] Timed.** Exercise tests must be timed, and mix questions from all covered lessons without showing the skill name.
19. **[change] Question mix.** The system must pick questions in these proportions:

    | Exercise test | Weak skills | Other covered skills |
    |---|---|---|
    | 1 | 60% | 40% |
    | 2 | 30% | 70% |

    "Weak skill" = a skill in the "learning" state, or one the student answered wrong in a previous exercise test.
    Skills in the "not started" state must not appear; instead, the card must list them as "practice these first".
    If the student has fewer weak skills than needed, fill the rest from the other covered skills.
20. **[exists] Result links back.** After an exercise test, the system must show the weak skills it found and link each one to its place in the path.

### 4.5 Simulation test (מבחן סימולציה)

21. **[new] Required, one attempt.** Every student must take one simulation test per real test. It can be taken only once.
22. **[new] Like the real test.** The simulation must cover all the lessons of the real test, with the same number of questions and the same time limit as the real test,
    no skill names, and no feedback until the end.
23. **[new] Window.** The simulation becomes available ~5 days before the test and stays available until the test day.
    It must be shown as **required** on the student's home screen until it is taken.
24. **[new] After the simulation,** the system must list the skills that failed and turn them into the review tasks of the last days (requirement 13).

### 4.6 Readiness meter

25. **[change] Readiness meter.** For each upcoming test, the system must show the student (and the teacher) a readiness meter made of:
    - % of the covered skills that are mastered;
    - the best grade of each exercise test;
    - the simulation test grade (once taken).
    *Today the test-prep screen shows readiness per skill and recent quiz grades.*

### 4.7 Student screens

26. **[exists] Home:** my assignments (המשימות שלי) from the teacher; the upcoming-test reminder (requirement 14); continue the path.
27. **[exists] Path:** all lessons and skills.
28. **[exists] Grades:** all quiz, exercise test and homework grades.
29. **[exists] Collection:** stars, constellations, and the class test calendar.

### 4.8 Teacher screens

30. **[change] Give an assignment.** The teacher must be able to create an assignment and load its content from:
    - the computer (file upload: PDF or images) – **[exists]**;
    - a photo taken with the device camera – **[new]** for assignments (exists today only for lesson resources);
    - the classroom smart board – **[new]**.
31. **[exists] Check assignments.** The teacher must be able to open each student's submission, give a grade (0–100) and a note, or send it back for correction.
32. **[change] Tests tab.** The teacher must be able to set a test (requirement 12) and see, for each test, which students have taken the simulation test and which have not.
33. **[new] Class heat map.**
    - Rows: students. Columns: skills (grouped by lesson).
    - Each cell is colored by the skill state: not started / learning / mastered.
    - Tabs for the period: **Sep–Dec** and **Jan–Jun**. A period shows the skills of the lessons taught in it, and states as they were at the end of the period (or today, for the current period).
34. **[new] Student lesson coverage.**
    - Rows: students. Columns: lessons.
    - Each cell shows the % of the lesson's skills the student has mastered, and the student's quiz (בוחן) grade for that lesson.
    - Same period tabs: **Sep–Dec** and **Jan–Jun**.

## 5. Non-Goals (Out of Scope)

- Skills do not decay or need re-mastering over time.
- Lessons are never locked; the app does not force an order.
- The app does not grade the real school test or import its grades.
- The app does not replace the teacher's lesson plan or teach new material in class.
- No student-to-student features (chat, leaderboards).

## 6. Design Considerations

- Hebrew, right-to-left. Works on phones first.
- Keep the existing look: the path as constellations, a skill as a star, the collection tab.
- Mastered skills should look clearly different from "learning" ones (today: gold star). With fading removed, there is no "dim" star.
- Heat map colors must be readable in light and dark mode and must not rely on color alone (add a symbol or text in each cell).
- The "one task for today" on home must be a single, obvious button.

## 7. Technical Considerations

- Grades that matter (quiz, simulation) must be computed and stored on the server, so a student cannot change them from the device.
  Today some progress data (skill progress, practice tests) is reported by the student's device; the heat map and coverage views should mark device-reported data the same way the class report does today.
- Mastery (requirement 5) needs the date of each answer, so the server can check the "2 different days" rule.
- "Similar question" (requirement 4) requires each skill to have enough questions, or question templates with changing numbers.
- The simulation's timer must be kept on the server (like the end-of-lesson quiz today), so refreshing or closing the app does not reset it.
- Removing star fading affects existing code: the fading logic, "mixed review", and any "fading" status in the class report and test prep.

## 8. Success Metrics

- ≥ 90% of students take the simulation test before each real test.
- On test day, students have mastered on average ≥ 80% of the covered skills.
- ≥ 75% of students take both exercise tests before each real test.
- Teachers open the heat map or the coverage view at least once a week.

## 9. Open Questions

1. **Real test length:** to make the simulation "the same length and time as the real test", the teacher must enter the number of questions and the time limit when setting a test. Is that OK, or should there be a default (e.g. 12 questions, 90 minutes)?
2. **Which quiz grade** goes in the lesson coverage cell: the retakeable quiz's best grade, or the end-of-lesson summary quiz (בוחן מסכם) that exists today and is the lesson's official grade? Does the summary quiz stay in the product?
3. **Feedback in exercise tests:** immediate feedback after each question (better for learning), or only at the end (closer to the real test)? Today exercise tests 1 and 2 give feedback after each question.
4. **Smart board:** which board(s) does the school use, and how does content get from it into the app (export a file, share a link, screenshot)?
5. **Exercise test length and time limit:** same as the simulation, or shorter?
6. **Several tests at once:** if two tests overlap (e.g. a test in 5 days and another in 12), how should the home screen choose "today's task"?
