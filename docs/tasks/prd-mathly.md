# PRD: Mathly – Skill Mastery and Test Readiness

## 1. Introduction / Overview

Mathly is a math practice app for middle- and high-school students and their teachers.
Students often finish a topic without really mastering it, and then arrive at the school test unprepared:
they never practiced mixing topics, never worked under time pressure, and don't know where their gaps are.

This document describes the **whole app**, to be built from scratch. It is written so that a complete OpenSpec
specification can be derived from it, one capability per requirement group (see Appendix A).

The app has five roles (see 4.1):

- **Students** practice on **the path**, a self-paced route through every skill, drawn as a trail of stars
  (Duolingo-like). Each skill opens an **exercise screen** with a **smart board** for working out solutions.
  When the teacher sets a real test, **the test countdown** plans the student's last weeks before it:
  finish the path, take two exercise tests, take one simulation test, and review what failed.
  Students can also get help with a photographed problem and have handwritten answers checked, always through their teacher.
- **Teachers** give and check assignments, set tests, review the AI's checks of their students' work, and see the
  progress of the classes they teach, per skill and per lesson.
- **Managers** create the classes: name, teacher and students.
- **Admins** give roles to accounts.
- **Developers** (the app's operators) have every permission and the developer tools.

Everything described here that is not about **quizzes and tests** (4.9–4.13) has a working reference
implementation in the earlier app, called **mathly1** (the code in `app/` and `static/`). Requirements marked
*Reference* name the place to read its behavior. Only the **exercise bank** and the **smart board** are
reused as files (see 7.1); everything else is rebuilt.

### Glossary

| Term | Hebrew | Meaning |
|---|---|---|
| skill | מיומנות | A specific topic, e.g. פירוק טרינום. Shown on the path as a star |
| exercise | תרגיל | A question on a certain topic. Can be either open-ended or multiple choice |
| lesson | שיעור | A set of skills, e.g. טכניקה אלגברית 1. Shown on the path as a hub with its skills around it |
| class | כיתה | A named group of students with one teacher. Every class studies the whole course |
| quiz | בוחן | A test on a single lesson. Can be retaken; best grade wins; each retake draws new questions. It is the only quiz type (no one-time summary quiz); its best grade is the lesson's grade |
| exercise test | מבחן תרגול | A timed test on a set of lessons. Can be retaken; best grade wins |
| simulation test | מבחן סימולציה | A timed test on a set of lessons. One time only |
| test | מבחן | The real-life test. Appears in the app as a date + the lessons it covers + number of questions and time limit (default 12 questions, 45 minutes). Set by the teacher |
| smart board | לוח | The drawing board on which a student or teacher writes and draws a solution |
| comet | שביט | A rare shooting star that crosses the screen during practice and can be caught for the collection |
| AI queue | תור ה־AI | The list of a class's student requests (a photographed problem, an answer to check) that wait for the teacher to send them to the AI or decline them |
| student / teacher / manager / admin / developer | תלמיד / מורה / מנהל כיתות / מנהל הרשאות / מפתח | The five roles (see 4.1) |

## 2. Goals

1. Help every student **master each skill**: mastery is proven, not assumed (3 correct in a row, no hints, on 2 different days).
2. Help every student **get ready for the real test**: on the test day, the student has mastered the covered skills,
   practiced mixed and timed questions, and taken one full simulation.
3. Give the teacher a clear, per-student picture of **which skills and lessons** each student has covered.
4. Make practice something students come back to: a clear path, instant feedback, a daily goal, a streak and a collection.
5. Give students help and feedback on written work without students ever calling the AI themselves, and keep the AI's cost under the teacher's and the class's control.

## 3. User Stories

**Student**
- As a student, I want to sign in with my Google account and land on my path, so I can start without setting anything up.
- As a student, I want to see all my lessons as a trail of stars, with the next skill marked, so I always know where to continue.
- As a student, I want to open any lesson at any time, so I can follow what my class is learning.
- As a student, I want instant feedback on every answer, and when I'm wrong I want to know *what* my mistake was and get a different question, so I really learn it and don't just memorize the answer.
- As a student, I want a help button with the explanation and a solved example, so I can get unstuck.
- As a student, I want to solve on a smart board beside or over the question, so I can work out a full solution and hand it in.
- As a student, I want to photograph a problem I'm stuck on and get hints one at a time, so I can learn instead of just copying the answer.
- As a student, I want my handwritten answer checked, and to ask my teacher to look again if I disagree.
- As a student, I want to see how many days are left until my test, how ready I am, and what to do today, so I don't have to plan by myself.
- As a student, I want to practice with timed, mixed tests before the real test, so the real test doesn't surprise me.
- As a student, I want one full simulation of the real test, so I know where I stand while there is still time to fix gaps.
- As a student, I want to catch comets and fill my collection of stars and constellations, so practice feels like a game.

**Teacher**
- As a teacher, I want to sign in and see my classes and their students' progress, so I know where each student stands.
- As a teacher, I want to give an assignment from a file, from a photo, or by writing it on the smart board, so I can use whatever material I already have.
- As a teacher, I want one inbox of everything my students handed in that waits for me, so I don't miss anything.
- As a teacher, I want to review my students' AI requests and send the good ones, so students get help while I keep control and the cost stays low.
- As a teacher, I want to check submitted work and give a grade and feedback, and to see the AI's suggested grade first.
- As a teacher, I want to add and remove the students of my own class, so a new student can start without waiting for a manager.
- As a teacher, I want to set a test date and the lessons it covers, so the app prepares my students for it.
- As a teacher, I want to see who has taken the simulation test.
- As a teacher, I want each student's progress per lesson, so I can see at a glance which lessons the class struggles with.
- As a teacher, I want to see how much of each lesson each student has covered.

**Manager**
- As a manager, I want to create a class with its teacher and its students, so a new group can start practicing.
- As a manager, I want to edit or delete a class and set its daily AI budget, so I can keep rosters and costs right.

**Admin**
- As an admin, I want to give an account a role, or take it away, so the right people can do their jobs.

**Developer**
- As a developer, I want every permission, so I can help whoever cannot get in or do something.
- As a developer, I want to see what the AI costs, so the budget stays predictable.
- As a developer, I want my own tools (a text prompter and a lab), so I can prepare and test.

## 4. Functional Requirements

Requirements are grouped; each id (for example `ACC-3`) is stable and is what OpenSpec requirements refer to.

### 4.1 Accounts, sign-in and roles (ACC)

*Reference: `static/index.html` (`#boot`, the sign-in page), `static/math.js` `boot()`, `app/access.py`, `app/auth.py`.*

- **ACC-1 Sign-in page.** Before sign-in the only screen is the sign-in page: the app's logo ("לומדים בכיף", the animated logo of mathly1) and mascot, one line of status text,
  and one button "כניסה עם Google". The app must not show or serve any student content, class or progress before sign-in.
- **ACC-2 Google sign-in.** Everyone signs in with their Google account. The session stays on the device,
  so the person does not sign in at every visit. Sign-out is available on every screen.
- **ACC-3 Roles.** There are five roles: **student**, **teacher**, **manager**, **admin**, **developer**. The server decides a signed-in email's roles on every request, never the device:
  - developer: the email is in the app's developer list (a setting);
  - teacher: the email is in the app's teacher list (a setting), or is named as a class's teacher, or was given the role (ADM-1);
  - manager and admin: the role was given to the account (ADM-1); the app's settings can name the first admins;
  - student: any other email.
  One person may hold more than one role and then gets the screens of each.
- **ACC-4 Permissions.**

  | Role | Can |
  |---|---|
  | student | use the path and everything of their own: answers, grades, assignments, requests |
  | teacher | see the progress, results, grades, assignments, tests and AI queue of the students of the classes they teach, and nobody else's; add and remove the students of those classes (TCH-9) |
  | manager | create, edit and delete classes, set a class's AI budget, and see the list of classes and students. No learning data |
  | admin | give and take away roles of accounts. No learning data |
  | developer | everything, for every class and every account, plus the developer tools (4.20) |
- **ACC-5 Student in no class.** A signed-in student who is in no class sees a message that their account is not in a class and to ask their teacher or a manager to add them, with the email they signed in with,
  and nothing else. When no class exists yet, the same message shows.
- **ACC-6 First sign-in.** The first time a student signs in, their account is linked to the entry the manager made for their email.
- **ACC-7 Failure messages.** When the sign-in service cannot be reached, the page says so and lets the person try again.
  When a session has expired, the person is returned to the sign-in page with a short message.
- **ACC-8 Every request is checked.** The server checks the sign-in and the role on every request except the health check; a request without a valid sign-in, or outside the caller's permissions, is refused.
- **ACC-9 Role switcher.** A person with more than one role gets a chip for each role in the header, each opening that role's home; a developer gets all five; a person with one role sees no chips.
  The last role chosen is remembered on the device. A link or a reload lands on the screen it points to, and switching role clears the address.

### 4.2 Classes (CLS)

*Reference: `static/math.js` `manageClasses`, `drawManagedClasses`, `openClassEditor`; `app/main.py` `/api/classes`.*

- **CLS-1 Who manages classes.** Only a manager (and a developer) can create, edit and delete classes. They do it in the classes screen (MGR-1).
  A class's teacher can also add and remove the students of that class, and nothing else about it (TCH-9).
- **CLS-2 A class** has: a **name** (1–80 characters, unique ignoring case), its **students** (email addresses), one **teacher** (an email address), an **AI switch** (off for a new class; see AI-10) and a **daily AI budget** (a number of AI checks a day, default 150, used only while the AI is on).
- **CLS-3 Adding students.** The manager (or the class's teacher) pastes email addresses, one per line (commas and spaces also separate them). Repeated addresses are ignored and
  invalid ones are reported. A student may belong to more than one class.
- **CLS-4 The teacher.** A class has at most one teacher, given by email. A teacher is never also a student of the same class. A teacher may teach several classes.
- **CLS-5 Editing.** The manager can change a class's name, students, teacher and AI budget. Removing a student from a class does not delete that student's progress.
- **CLS-6 Deleting.** The manager can delete a class after confirming. Deleting a class does not delete its students' progress.
- **CLS-7 Class list.** The list shows, for each class, its name, number of students and their emails, and its teacher, with shortcuts to edit and delete.
- **CLS-8 Lessons in the path.** A class has no chosen lessons: every class studies every lesson of the bank, one course called "מתמטיקה כיתה ט - מצוינות". A student in at least one class sees every lesson in the path.
  Within those lessons everything is open (PTH-4).

### 4.3 The exercise bank (BNK)

- **BNK-1 Content.** The app's content is the exercise bank described in 7.1: lessons, skills, questions and mistakes.
  Every question has exactly one correct choice; every wrong choice names a mistake; every mistake has a name and a tip.
- **BNK-2 Checked when the app starts.** The bank is checked when the server starts (unique ids, one correct choice per question,
  every mistake and skill referred to exists). A broken bank stops the server from starting and says what is wrong.
- **BNK-3 Math and figures.** Math written as `$…$` in the bank is shown as formulas. Questions that have a figure (geometry) or a graph show it.
- **BNK-4 No answers on the device.** A practice question sent to the device carries no sign of which choice is correct.
  The server grades.
- **BNK-6 Ten practice questions.** Practice on the exercise screen uses 10 questions per skill: the first 10 of the skill's questions in the bank (five skills have 30). The other questions stay in the bank and are still drawn by quizzes, exercise tests and the simulation.
- **BNK-5 Bank content tools.** A tool lists what the bank still lacks (see 7.3).

### 4.4 The path (PTH)

*Reference: `static/math.js` `pathView`, `orbitRing`, `status`/`next`; `static/math-sky.js` (the owl, the spark/star); the `.mx-trail` / `.mx-star` styles in `static/math.css`.*

The path is the student's main screen: a trail of stars.

- **PTH-1 Layout.** Every lesson is a **hub** that shows its name and "mastered of total". The lesson's skills sit around the hub in a **ring**,
  in order, numbered from the top and clockwise. The hubs are joined by a vertical **trail** from a start marker (with the mascot) to an end marker.
  After a lesson's ring comes its **quiz** (4.9) as a node on the trail.
- **PTH-2 Stars and states.** Each skill is a star showing its state: **not started**, **learning** or **mastered** (4.7).
  A mastered skill looks clearly different from the other two. The state is also shown with a symbol and a word under the star
  ("○ לא התחלת", "◐ בלמידה", "✓ נשלטה"), never by color alone. A mastered star that has faded (MST-8) shows its dimmed look and the word "דועך" as well.
- **PTH-3 Next skill.** One skill is marked as the suggested next, with the mascot perched on its star: the unmastered skill the student answered most recently,
  or else the first unmastered skill in the bank's order. When everything is mastered nothing is marked. The marker is a suggestion: it never locks, hides or reorders anything.
- **PTH-4 All open.** The student can open any lesson, and any skill inside it, at any time, in any order. Nothing is ever locked.
- **PTH-5 Opening a skill.** Tapping a star opens that skill's exercise screen (4.5) over the path. Closing it returns to the path with the star updated.
  When the path opens, it scrolls to the next skill.
- **PTH-6 Top of the path.** The path shows today's progress toward the daily goal and the current streak (MST-6).
- **PTH-7 Accessibility.** Each star is a control whose accessible name is its number, the skill's name and its state in words. It can be reached and opened from the keyboard.
  Animations stop when the device asks for reduced motion. The path is dark, like the rest of the app.
- **PTH-9 Choosing a subject.** After sign-in a student first sees the subjects of their classes as cards (as in mathly1), each with an icon, the subject's name
  and a bar "N מתוך M מיומנויות" (skills mastered of all skills in the student's lessons). Today the only subject is math, named "מתמטיקה כיתה ט - מצוינות", so there is one card.
  Tapping a card opens that subject's home (STU-1, as in mathly1), and the tab bar leads from there to the path, the submissions, the grades and the collection; the subject's screens have a way back to the subjects. A reload or a link to a skill (`#/skill/…`) opens its path directly.
- **PTH-10 Completed lessons.** A lesson is **completed** when every one of its skills is mastered (about 50 exercises: five skills of ten questions), or when its quiz was passed (QZ-7). The hub says "הושלם".
- **PTH-11 The curriculum.** Each lesson may have a **date** by which it should be completed, one curriculum for the whole school, set by a manager (MGR-3). The path marks every lesson that should be finished by now: its date has passed and it is not completed. The hub shows a marker and "היה אמור להסתיים ב־<date>", and the top of the path says how many lessons are behind. A lesson without a date, with a date ahead, or completed is not marked. Nothing is locked (PTH-4).
- **PTH-8 Phone first.** The path fits a 360px-wide screen without sideways scrolling, including the lesson with the most skills.

### 4.5 The exercise screen (EXR)

*Reference: `static/math.js` `open()` and `answer()` (the skill sheet), `choiceButtons`, `figures`, `autoAdvance`.*

The exercise screen is where a student practices one skill.

- **EXR-1 Layout.** It opens as a sheet over the path. The header shows the lesson's name, the skill's name, a completed mark when the skill is mastered,
  a button for the smart board (4.6), a help button "?" and a close button. Under the header is the skill's short explanation.
- **EXR-2 The question.** The sheet shows one question at a time: its text with formulas, its figure or graph if it has one, and its choices.
  The choices appear in a new random order each time the question is shown. A line "question n of N" and a row of N dots show how far the student is in the round of the skill's practice questions (BNK-6: at most 10): a dot is filled for a right answer, marked for a wrong one, and empty for a question not answered yet.
- **EXR-3 Answering.** The student taps a choice. The server grades it and the sheet answers at once. While the server is checking, the tapped choice shows a spinner, a line says "בודקים…" and the other choices are dimmed and cannot be tapped; with reduced motion the words stay and the spinner is still.
- **EXR-4 A right answer.** A right answer gets a short celebration (an animation; sound and vibration where the device allows) and the count of right answers in a row.
  After a short countdown the next question appears; the student can skip the countdown or cancel it.
- **EXR-5 A wrong answer.** A wrong answer is quiet. The feedback names the specific mistake attached to the chosen choice in the bank (its name and its tip,
  for example "טעות סימן באיבר האמצעי"), talks about the mistake and not about the student, and does **not** reveal the correct answer. The chosen choice is marked on the choice itself with a symbol and a word ("✗ לא נכון"), not by colour alone; no other choice is marked.
  When the mistake names a skill to go back to, the feedback links to it. The next question is a **different** question on the same skill (a skill with one question repeats it).
- **EXR-6 Which question comes next.** Practice on a skill is a **round**: the skill's practice questions (at most 10), each shown once in a random order (EXR-12). The next question is one of the round that was not answered yet; a wrong question does not come back in the round.
- **EXR-7 Help.** The help button shows the skill's explanation and, where the bank has one, a solved example. Opening help before answering means that answer **does not count**
  toward mastery (it neither counts nor breaks the run; see MST-3). It still counts toward the daily goal.
  Help is a ladder: the "?" gives instant help (explanation and solved example); if that is not enough, its last line offers "עדיין תקועים? צלמו" and opens photo help (STU-6) when the class has the AI on.
- **EXR-8 Related skills.** The sheet shows the skills this one requires and the skills it opens, as tappable chips. They are links, not locks.
- **EXR-9 Resuming.** Reopening a skill continues with the question that was on screen.
- **EXR-10 Skills without questions.** A skill with no questions says there is no practice for it yet, and cannot be mastered.
- **EXR-11 Comets.** Comets can cross the exercise screen (CMT-1).
- **EXR-12 Rounds.** After the last answer of a round (EXR-6) the sheet shows the result "N מתוך 10" and, for each wrong answer, the question, the mistake's name and tip and a link to the skill to go back to (never the correct answers). It offers "סבב חדש" (all the questions again in a new order) and a way back to the path. The server remembers the round: leaving and coming back continues it, and a finished round shows its result until a new one starts. Mastery (MST-2) is counted across rounds.

### 4.6 The smart board (BRD)

*Reference (kept as files): `static/math-board.js`, `static/board-math.js`, `static/vendor/mathlive/`. It exposes `window.MathlyBoard`.*

- **BRD-1 Where it is available.** On the exercise screen, in quizzes and tests, in assignments the student hands in, and where the teacher writes an assignment.
  A button in the sheet's header opens it.
- **BRD-2 Placement.** On a desktop screen the board sits **beside** the exercise; the device remembers whether it is on.
  On a phone or tablet it opens **full screen** over the exercise from the same button, and closes back to the question.
- **BRD-3 Tools.** Move; **pen** (three ink colors; follows pen pressure); straight **line**; **circle** (dragged from its center);
  **angle** (pointing at a corner where two lines meet shows the arc; a click adds it and asks for its words; a number gets a degree sign;
  one, two or three arcs or a right-angle square); typed **math** (a math keyboard set up for ninth grade: digits, x and y, fractions, powers, roots, brackets, absolute value,
  ± ≤ ≥ ≠, π, degrees, angle and triangle signs, and a letters tab); **eraser** (three sizes); **undo**; and **clear**.
- **BRD-4 Everything is an object.** Every pen stroke, line, circle, angle and formula on the board can be selected, moved and erased.
- **BRD-5 Snapping.** Line ends and circle centers snap to ends and centers already drawn, so a triangle closes neatly; lines that meet that way move together.
  The eraser removes the lines and circles it touches and cuts pen strokes.
- **BRD-6 The question on the board.** A copy of the question (its text and figures) can be placed on the board. The eraser leaves it alone; select it and delete it instead.
- **BRD-7 Endless paper.** The paper grows downward and to the right. The mouse wheel scrolls it (sideways with Shift or a trackpad); two fingers scroll in any direction while one finger draws;
  dragging empty paper with the move tool scrolls too.
- **BRD-8 Pen and palm.** Once a pen has touched the screen, a single finger is ignored. While the pen writes (and a moment after) every touch is ignored, and a wide contact is treated as a palm.
- **BRD-9 Sketches stay local.** Each question keeps its own sketch as long as the page is open. Nothing is sent anywhere unless the student hands it in.
- **BRD-10 Handing in.** Where a question needs a written solution (assignments), the sketch becomes a picture that the student hands in from the board (see ANS-1).
- **BRD-11 Calculator.** A scientific calculator (the layout of a Casio fx-991ES PLUS, with SHIFT functions) opens on a panel over a corner of the paper from a toolbar button.
  It is available everywhere the board is, including quizzes, exercise tests and the simulation.
- **BRD-12 Labels.** Every tool has a Hebrew label and a line icon; the board works with touch, pen and mouse.

### 4.7 Skill states, mastery, daily goal and collection (MST)

*Reference for fading and the collection: `static/math-sky.js`.*

- **MST-1 Skill states.** Every skill, for every student, is in exactly one state: **not started** (no answers yet), **learning** (at least one answer, not yet mastered)
  or **mastered** (met MST-2).
- **MST-2 Mastery.** A skill becomes **mastered** when the student answers 3 questions on it correctly in a row, each on the first try and without opening help,
  and these answers fall on at least 2 different calendar days.
- **MST-3 Help does not break the run.** An answer given after opening help is skipped for mastery: it neither counts toward the 3 nor breaks the run.
  A wrong answer restarts the run.
- **MST-4 Mastery does not decay.** A mastered skill stays mastered. It does not need re-mastering over time, even after later wrong answers.
  The readiness meter, the exercise tests and the teacher's progress by lesson all use this state.
- **MST-5 The server decides.** The server stores the date of every answer (the calendar day in Israel, decided by the server, never by the device) and decides mastery from it.
- **MST-6 Daily goal and streak.** 5 correct answers in a day make a streak day. The path shows today's count and the number of days in a row.
  A streak is kept through the morning of a new day and counted up to yesterday until the new day's 5 are reached.
- **MST-7 Collection.** A collection screen shows what the student achieved: each mastered skill as a star, each completed lesson (all of its skills mastered)
  as a constellation drawn from its stars, and the comets caught (CMT-3).
- **MST-8 Fading stars.** A mastered skill the student has not answered for 14 days has a **faded** star: it dims and says "דועך". One answer on the skill (correct or not) relights it.
  Fading is only a review cue: the skill is still mastered (MST-4), so the readiness meter, the teacher's progress and exercise tests are unchanged.

### 4.8 Comets (CMT)

*Reference: `static/math-sky.js` (`COMETS`, `cometDue`, `catchComet`).*

- **CMT-1 A comet crosses.** After a right answer on the exercise screen a comet may cross the screen for a few seconds. At most one comet comes in a day.
  The first comet comes surely the first time the student reaches the daily goal (MST-6), which can happen in the first session, so the reward arrives early;
  after that each right answer has a small chance (about 12%) while there are comets left to catch.
- **CMT-2 Catching.** Tapping the comet while it crosses catches it. A caught comet is one the student does not yet have, picked at random. The catch shows the comet's name and a short fact.
  Comets stop when the student has all of them. Comets never change a skill's state, a grade or the streak.
- **CMT-3 The comets.** There are twelve: π, Fibonacci, the golden ratio, infinity, e, √2, zero, Pythagoras, primes, Pascal's triangle, Euler's formula and the Möbius strip.
  Each has a symbol, a name and a fact in Hebrew. The collection shows each caught comet with its fact, and each missing one as "?" with "עוד לא נתפס".
- **CMT-4 Reduced motion.** With reduced motion, a comet does not cross; the student is offered it once as a tappable item.

### 4.9 Quizzes (בוחן) (QZ)

- **QZ-1 Quiz per lesson.** Every lesson has one quiz: the lesson's "boss level", a node on the trail after the lesson's ring. It is always open (PTH-4). The student can retake it at any time;
  the best grade counts, and the quiz's best grade is the lesson's grade.
- **QZ-2 Format.** A quiz is **15 multiple-choice questions** drawn from the bank questions of the lesson's skills, at least one per skill and the rest spread evenly across the skills, in **45 minutes** (3 minutes for each question). It is **passed** with a grade of at least 87 (13 right out of 15); a pass stays whatever a later retake scores (QZ-7).
  The timer runs on the server; when it ends the quiz is submitted as it stands and unanswered questions count as wrong. Skill names are not shown and there is no feedback until the end.
  The smart board and the calculator are available.
- **QZ-3 Retakes draw new questions.** Each retake prefers questions the student has not had in earlier attempts at this lesson's quiz, the least-used first. While the lesson has enough unused questions (four skills of ten give two quizzes in a row without a repeat), none repeats; after that the least-used come first.
- **QZ-7 Passing.** A quiz is passed with a grade of at least 87 (13 of 15). Passing completes the lesson (PTH-10) and does not change any skill's mastery.
- **QZ-4 After a quiz.** The student sees the grade, the skills where points were lost (each linked to its star, so they can practice before retaking) and, for each missed question, the name and tip of the mistake they made (as in EXR-5).
  The correct answers are never shown, so a retake tests understanding and not memory.
- **QZ-5 Grades on the server.** Quiz grades and timers are computed and stored on the server.
- **QZ-6 Written quizzes.** The four written quizzes authored in the bank (four written questions, 100 points, 45 minutes) are not lesson quizzes. A teacher can give one to a class as an assignment (TCH-2).

### 4.10 Test countdown (TST)

- **TST-1 Setting a test.** The teacher sets a test: date + the lessons it covers (+ an optional note), plus the real test's **number of questions** and **time limit**.
  These start with defaults (12 questions, 45 minutes) that the teacher can change.
- **TST-2 The countdown plan.** From the moment a test is set, the system shows the student a plan that depends on the days left:

  | Days before the test | What the app asks the student to do |
  |---|---|
  | until 9 | Finish the path for every covered lesson (bring every covered skill to "mastered") |
  | ~9 | Exercise test 1 |
  | ~7 | Exercise test 2 |
  | ~5 | Simulation test (required) |
  | 4 → 1 | Review the skills that failed in the simulation; light mixed review the day before |

  The day numbers are **recommendations**: the student can start each step earlier or later.
  If the test is set less than 9 days ahead, the system keeps the same order and shortens the gaps evenly.
- **TST-3 Home screen reminder.** The home screen shows, for the nearest test: days left, the readiness meter (RDY-1), and **one task for today** taken from the plan.
  When several tests are coming up, "today's task" comes from the **closest** one.

### 4.11 Exercise tests (מבחן תרגול) (EXT)

- **EXT-1 Created by the app.** When the teacher sets a test, the system creates 2 exercise tests for every student in the class and places them on the student's countdown.
- **EXT-2 Teacher can assign one.** The teacher can send an exercise test to the whole class as an assignment (built with the assignments, stage 6): it shows in "המשימות שלי", opens the exercise test and counts as done when the student has taken it; it is not handed in as a picture.
- **EXT-3 Retakes.** The student can start or retake an exercise test at any time. Each retake draws new questions; the best grade counts.
- **EXT-4 Like the simulation.** Exercise tests have the same number of questions and the same time limit as the simulation (that is, as the real test, TST-1),
  mix questions from all covered lessons, and do not show the skill name. Feedback comes **only at the end**, not after each question.
- **EXT-5 Question mix.** The system picks questions in these proportions:

  | Exercise test | Weak skills | Other covered skills |
  |---|---|---|
  | 1 | 60% | 40% |
  | 2 | 30% | 70% |

  "Weak skill" = a skill in the "learning" state, or one the student answered wrong in a previous exercise test.
  Skills in the "not started" state do not appear; instead, the card lists them as "practice these first".
  If the student has fewer weak skills than needed, the rest comes from the other covered skills.
- **EXT-6 Result links back.** After an exercise test, the system shows the weak skills it found and links each one to its star on the path.
- **EXT-7 Grades on the server.** Exercise test grades and the timer are computed and kept on the server.

### 4.12 Simulation test (מבחן סימולציה) (SIM)

- **SIM-1 Required, one attempt.** Every student takes one simulation test per real test. It can be taken only once.
- **SIM-2 Like the real test.** The simulation covers all the lessons of the real test, with the number of questions and the time limit the teacher set for it (TST-1),
  no skill names, and no feedback until the end.
- **SIM-3 Window.** The simulation becomes available ~5 days before the test and stays available until the test day.
  It is shown as **required** on the student's home screen until it is taken.
- **SIM-4 Server timer.** The timer is kept on the server, so refreshing or closing the app does not reset it. The grade is stored on the server.
- **SIM-5 After the simulation,** the system lists the skills that failed and turns them into the review tasks of the last days (TST-2).

### 4.13 Grades and readiness meter (GRD, RDY)

- **GRD-1 One scale.** Every grade (quiz, exercise test, simulation, assignment) is a whole number from 0 to 100. In a multiple-choice quiz or test every question is worth the same, and the grade is the share of right answers, rounded.
  Teachers' grades for assignments are on the same scale.
- **GRD-2 When time ends.** When a timer ends (quiz, exercise test, simulation) the attempt is submitted as it stands, and unanswered questions count as wrong.
  Leaving the screen does not stop the timer.
- **RDY-1 Readiness meter.** For each upcoming test, the system shows the student (and the teacher) one **readiness number from 0 to 100**, drawn as a level bar, with its three parts under it:
  - **M**: the % of the covered skills that are mastered;
  - **E**: the average of the best grade of each exercise test taken;
  - **S**: the simulation test grade (once taken).
- **RDY-2 How the number is made.** It is the weighted average of the parts that exist, with weights M 50, E 20, S 30; a part that does not exist yet (no exercise test taken, no simulation) is left out and the others are scaled up.
- **RDY-3 No false confidence.** Until the simulation is taken the number is capped at 80, and the bar says so. The bar's label by number is: 0–39 "מתחילים", 40–69 "בדרך", 70–84 "כמעט שם", 85–100 "מוכנים". "מוכנים" can only show after the simulation.
- **RDY-4 The number explains itself.** An info button "ⓘ" beside the number opens a short tooltip (hover, focus or tap; closes on a second tap, a tap elsewhere or Escape): the number is made of mastery (50%), practice tests (20%) and the simulation (30%); a part with no grade yet is left out; without the simulation it cannot pass 80.

### 4.14 Handwritten answers and phone photos (ANS, PSH)

*Reference: `static/answer-scans.js`, `app/answer_scans.py`, `app/answer_routes.py`, `app/answer_cleanup.py`, `app/push.py`, `static/service-worker.js`.*

- **ANS-1 Handing in a written answer.** A written answer is handed in as a picture: from the smart board (BRD-10), or by photographing the paper. On a phone the camera opens;
  on a computer the student uploads an image or asks their own phone to take the photo (ANS-2).
- **ANS-2 Photo request to the phone.** The computer creates a photo request for one answer. The student's phone, signed in to the same account, shows the request's window with a **4-digit code**
  that the student matches against the computer; the student photographs the answer there. The computer shows the request's state: waiting for the phone, uploading, received, failed, expired or replaced by a newer request.
  A request expires after a while and a newer request for the same answer replaces an older one.
- **ANS-3 Where the pictures live.** Answer pictures are kept in private storage tied to the account and are read only by the server. The server removes, every hour, pictures no answer refers to.
  Pictures are kept until the end of the school year (31 August) and then removed; the grade and the teacher's comment stay. A teacher of the class, a manager or a developer can delete a student's pictures earlier on request.
- **PSH-1 Notification to the phone.** A phone can turn notifications on. When the computer asks for a photo of an answer, the phone is notified even if the app is closed; tapping the notification opens the app on the request's window.
- **PSH-2 Which devices.** Only phones subscribe; the computer that made the request gets no notification. A subscription the push service no longer knows is deleted. On an iPhone, notifications work only from the app added to the home screen (iOS 16.4 or later).
  The server's push key is a setting; changing it drops every subscription, and each phone turns notifications on again.

### 4.15 The AI (AI)

*Reference: `app/math_photo.py`, `app/answer_grading.py`, `app/ai_queue.py`, `app/ai_batches.py`, `app/teacher_ai.py`, `app/ai_usage.py`, `app/teacher_review.py`, `app/homework_grading.py`.*

- **AI-1 Students never call the AI.** A student's request (a photographed problem, or an answer to check) becomes a request in the AI queue of the class's teacher. The teacher looks at the picture and either sends it to the AI or declines it
  with an optional note. The student's page shows the request waiting (it looks for the answer every few seconds while it is open), and then its result or the teacher's note. The student can cancel a waiting request.
  A student has at most 5 requests waiting at once and at most 20 photos a day.
  A student in more than one class chooses which teacher a request goes to, defaulting to the teacher of the class with the nearest upcoming test and then to the one used last. The request counts against that class's budget.
- **AI-2 Who sends straight.** A teacher or a developer sends without the queue when the request is their own. Everyone else's requests wait in the queue; a teacher sees the queue of their classes' students and a developer sees every queue.
- **AI-11 How it runs.** A send marks the request "processing" and returns at once; the AI is called from a small background pool and the pages look again every few seconds while open. After a server restart, requests that were being processed wait again. A help photo is stored privately like an answer picture and is deleted when the AI has answered, or the request is declined or cancelled; after a failure it is kept for the retry. Settings: `ANTHROPIC_API_KEY` (without it a send fails with "missing key") and `MATH_MODEL` (optional).
- **AI-3 Photographed-problem help.** The student photographs a problem. The AI reads it and solves it, and answers in a fixed shape: the problem as it read it (so the student can check the reading), the solution as steps, each with a **hint** that does not give the step away and the step itself,
  the final answer, and the skill on the path that the problem practises (linked to its star). The page shows the hints one by one, and the steps and the answer only when the student asks for them. The photo is sent to the AI and is not kept.
- **AI-4 Checking handwritten answers.** The AI checks a saved handwritten answer against the question as it was when the student answered it (a stored copy, so later changes to the bank do not change an old grade), and returns a score and a comment.
  This is a **suggestion** to the teacher. Where an answer's score is used, the teacher's score wins over the AI's. The AI's check is never edited: the teacher's review is kept next to it, the latest review counts, and older ones stay as history.
- **AI-5 Asking the teacher to look again.** A student who disagrees with a check asks the teacher to look again; there is at most one open request per answer and five per student. Saving a review closes the request.
- **AI-6 Budgets.** Each class has a daily number of AI checks of its students' work (CLS-2), counted by the Israel date and taken in one step in the database, so two batches at once never pass it. A check that fails, or whose picture the AI could not read, is given back.
  A teacher also has a personal allowance of 3 AI requests a day for their own use (a problem they photograph, an answer of their own they check, or a student's request they send). Developers have no limit. Students are not counted.
- **AI-7 Batches.** A teacher can send every pending check of one scope in a single action, oldest first: one assignment's submissions, or the single answers waiting. When the budget is short it sends what is left and the rest stays pending for the next day.
- **AI-8 When the AI fails.** The people who can fix it (the teacher who sent it, a developer) see what happened and what to do for each cause: missing key, invalid key, no permission, model not found, no credit, rate limit, overloaded, no connection, refused, cut short, or an unusable answer, with the technical detail.
  The student sees a short "try again later".
- **AI-9 Usage and cost.** Every AI call records its tokens and an estimated cost. Developers can see the totals (DEV-4).
- **AI-10 Privacy.** The AI is **off for a class** until a manager switches it on for that class, which the school does only after it has confirmed that families agree to an outside AI looking at their children's work.
  A student of a class with the AI off sees no AI buttons. Nothing that names a student (name or email) is sent to the AI: only the picture and the question. Before a first photo the student sees a reminder not to write their name or personal details in it.

### 4.16 Student screens (STU)

A tab bar at the bottom of the screen leads between them: home, path, submissions (STU-7), grades, collection and review (STU-8).

- **STU-1 Home** shows only what is critical: the nearest test's reminder with its readiness, today's task (TST-3) and **its practice tests below the pass line** (taken and with a best grade below 87, i.e. 13 of 15: each a button to take it again with the best grade as a chip inside it; one not taken yet, or at 87 or more, is not listed; other tests' practice tests are on their own cards), a required simulation, **every lesson behind the curriculum** (PTH-11; earliest date first, each kept short: its name, its date, a link named just "בוחן" with the best grade as a chip inside the link, a bare number or "-" when there is none; PTH-10), the **new** assignments (המשימות שלי: not handed in yet), and a button that continues the path at the next skill; my AI requests and their state (AI-1).
- **STU-2 Path:** see 4.4.
- **STU-3 Grades:** all quiz (best grade), exercise test, simulation and assignment grades.
- **STU-4 Collection:** see MST-7.
- **STU-5 Assignments.** The student opens an assignment, works on it (on the smart board, or by photographing paper; ANS-1) and hands it in; they see the teacher's grade and note, or that it was sent back for correction.
- **STU-8 Review tab (חזרה).** Every wrong answer goes to the student's review list: in path practice, in a lesson quiz, in a practice test and in the simulation; a question left unanswered when a quiz or a test is submitted or times out also goes there. A question already in the list is not added again. Answers given before the tab existed are not added.
  The tab says how many questions wait and shows **every waiting question as a card, grouped by skill**: a heading per skill (with its lesson and how many cards it holds), the skills in the bank's order and each skill's cards oldest first; a skill with nothing waiting has no heading. A card is answered in place. A **right** answer marks it done and removes the question (and the skill's heading when it was the last). A **wrong** answer keeps it, names the mistake and its tip (as in EXR-5), never shows the right choice, and offers "נסו שוב"; the right choice is not sent to the page before the answer.
  Redoing a question here is **practice only**: it does not change a skill's mastery, a grade, the readiness meter or a practice round; each right answer counts toward the daily goal (MST-6). An empty list says there is nothing to review.
- **STU-7 Submissions tab (הגשות).** Lists every assignment from the student's teachers, grouped by state: new, sent back for correction, handed in and waiting for a check, and checked (with the grade and note). Each opens its page; one past its due date and not handed in is marked "באיחור". The switch for phone notifications (PSH-1) is at the bottom of this tab, not on home.
- **STU-6 Photo help.** A camera button lets the student photograph a problem (AI-3). Pressing it opens the device's camera or gallery. The picture is shrunk on the device and its metadata is dropped before it is sent
  (JPEG, PNG or WebP). A sheet then shows the student's picture and the request's state, and the hints once the teacher has sent it.
  The button appears in two places, and only for students of a class with the AI on (AI-10):
  - on the **exercise screen**, in the header beside the "?" help; a request made there also tells the teacher which skill the student was on;
  - on the **home screen**, as a card "תקועים על תרגיל? צלמו אותו" that also shows the student's open requests and their state.
  It is not on the path, which stays a clean trail. The sheet says plainly that the teacher sees the picture first, so the student knows the answer is not instant.
  *mathly1 has no visible entry for this today (checked in a local run with sign-in off); this is new UI.*

### 4.17 Teacher screens (TCH)

- **TCH-1 Teacher home.** A teacher's home lists the classes they teach, each with its students and a shortcut to its progress. A teacher does not see the student path as their main screen. A teacher who teaches no class is told that a manager chooses who teaches each class. Each tab of the teacher's screen shows how many items are in it: classes, tests, assignments, and submissions waiting in the inbox.
- **TCH-2 Give an assignment.** The teacher creates an assignment (title, note, due date) and loads its content from:
  - the computer (file upload: PDF or images);
  - a photo taken with the device camera;
  - the smart board: the teacher writes or draws the assignment, and it is saved as the assignment's page(s);
  - one of the written quizzes authored in the bank (QZ-6).
- **TCH-3 Choosing who gets it.** An assignment goes to the whole class (or one class of those the teacher teaches).
- **TCH-4 Inbox and checking.** One inbox lists everything the teacher's students handed in that waits for them, oldest first: assignment submissions not checked yet (a returned one waits for the student)
  and open requests to look again (AI-5). The teacher opens each, sees the AI's suggested score and comment (AI-4) if there is one, gives a grade (0–100) and a note, or sends it back for correction.
- **TCH-5 AI queue.** The teacher sees their classes' AI requests (AI-1), with the picture, and sends or declines each, or sends a whole batch (AI-7). It is an **"AI" tab** on the teacher's screen with the number of waiting requests, and it also has the teacher's own photo help (AI-2) and what is being worked on, what failed and why (AI-8). A student asking to look again (AI-5) appears in the inbox (TCH-4), not here.
- **TCH-6 Tests tab.** The teacher sets a test (TST-1) and sees, for each test, which students have taken the simulation test and which have not.
- **TCH-7 Class progress, by lesson.** The teacher sees progress **per lesson, never per skill**.
  - Rows: students. Columns: lessons.
  - Each cell is short and shows three things only: a **progress bar** with the percent of the lesson's skills mastered written on it; the student's best quiz (בוחן) grade as a **bare number** (a dash for none, without the word); and, in the current period, a **warning mark** (⚠) when the lesson is behind the curriculum (PTH-11) and not completed. The lesson's state in words (הושלם PTH-10, בלמידה, לא התחילו, בפיגור) is the cell's accessible name, and a completed lesson's bar is gold.
  - Tabs for the period: **Sep–Dec** and **Jan–Jun**. A period shows the lessons of that period (by the lesson's date in the curriculum, PTH-11, else the last month of the bank's month for it), and states as they were at the end of the period (or today, for the current period). The current period opens first.
  - Where: a "התקדמות" tab on the teacher's screen (with its number: the students of the teacher's classes), also reached from a shortcut on each class card; one class at a time, with a picker when the teacher has several. Only the class's teacher and a developer can read it (never a manager or an admin).
  - The table scrolls inside its own frame with the student column fixed; the page does not scroll sideways. A student who has not signed in yet is all "not started".
- **TCH-8 (merged into TCH-7).** The coverage view is the progress by lesson above; there is no separate per-skill heat map.
- **TCH-10 Readiness per student.** For the class's nearest coming test: each student's readiness number and word (RDY), mastery percent, practice-test average and simulation grade, a dash for what is missing; a class with no coming test says so.
- **TCH-9 Roster of my class.** For each class they teach, the teacher can paste email addresses to add students and can remove a student (CLS-3, CLS-5). They cannot change the class's name, lessons, teacher or AI budget,
  and a teacher cannot add themselves as a student. Removing a student does not delete their progress.

### 4.18 Manager screens (MGR)

- **MGR-1 Classes.** The manager's home lists all classes (CLS-7) with a button for a new class, and an editor for creating and changing a class (CLS-2 – CLS-6). When a save is refused (for example the teacher is also one of the students), the editor says why right above the save button, in view, and keeps what was typed.
- **MGR-3 Curriculum.** A tab "תכנית לימודים" lists every lesson in the bank's order, with the bank's month as a hint and a date the manager can set, change or clear (PTH-11).
- **MGR-2 Students.** A list of all students with the classes each belongs to.

### 4.19 Admin screens (ADM)

- **ADM-1 Roles.** An admin sees the accounts the app knows (students from classes, teachers, managers, admins) and can give an account the role student, teacher, manager or admin, or take it away. The developer role is never given here; it comes only from the app's settings.
  Roles belong to an **email address**, so an admin can type an email that has never signed in and give it a role; the role takes effect at that person's first sign-in.
  The last admin cannot take away their own admin role. A role change shows within 30 seconds.
- **ADM-2 Own access.** A page shows the signed-in account's own roles and permissions.

### 4.20 Developer tools (DEV)

*Reference: `app/prompter.py`, `static/prompter.js`, and the management sheet in `static/math.js`.*

- **DEV-1 Every permission.** A developer can open any class's progress, tests, assignments, inbox and AI queue, as the class's teacher can, and everything managers and admins can do.
- **DEV-2 Prompter (פרומפטר).** A developer writes or pastes a text and shows it full screen as a scrolling teleprompter. Saved texts (a title up to 120 characters; up to 200 texts) belong to the account and are on every device; what is being edited is also kept in the browser, so nothing is lost before it is saved.
  Keys: space starts and stops, ↑/↓ change speed, +/− change size, M mirrors, F is full screen, Esc leaves; the mouse and a presentation remote work too.
  A saved text can have an **outline (ראשי פרקים)**: on request the AI rewrites the text as the same slides with two to four very short topic reminders each, once; it is kept with the text and can be edited. Changing the text without sending an outline drops the outline, so a stale one is never shown.
- **DEV-3 Lab (מעבדה).** A developers-only area for testing and development tools. In mathly1 it is an empty page that says tools will be added; the same here, until the first tool is chosen.
- **DEV-4 AI usage.** A page shows the AI's calls and estimated cost (AI-9): by day, by class and by kind of call.

## 5. Non-Goals (Out of Scope)

- Subjects other than math (the subject cards are built for them, but only math has content).
- Locked lessons or a forced order of lessons.
- Mastery that really decays: a faded star is only a cue (MST-8).
- Worked-example and faded-example stages before practice (the help button's explanation and solved example replace them).
- A one-time summary quiz (בוחן מסכם).
- Grading the real school test or importing its grades; a calendar of school tests (the teacher's test, TST-1, replaces it).
- Spaced-review cards, misconception-pattern cards, a teacher's preview of the student screens, monitoring dashboards, and a video library.
- Student-to-student features (chat, leaderboards).
- Students calling the AI directly.

## 6. Design Considerations

- Hebrew, right-to-left. Works on phones first; the teacher, manager, admin and developer views (progress by lesson, classes, roles) must also work well on a computer.
- The look follows the path's "sky" theme: a dark-blue night with aurora and starlight accents, gold for mastery, and an owl mascot that perches on the next skill. The app is always dark, as mathly1 is: the page background is a dark night with two soft glows and small fixed stars; it does not move. There is no light mode.
- A button whose action takes longer than about a third of a second shows it (a spinner, a second press ignored), everywhere in the app; with reduced motion it shows "…".
- Math is written in `$…$` text in the exercise bank; the app must render it as formulas.
- State and result never rely on color alone: every state has a symbol or a word (stars, progress cells, feedback).
- Mastered skills must look clearly different from "learning" and "not started" ones.
- Touch targets are at least 44px. Animations (stars, celebrations, comets) respect the device's reduced-motion setting.
- The "one task for today" on home is a single, obvious button.
- The smart board works with touch, pen and mouse, and keeps working when the device rotates.

## 7. Technical Considerations

### 7.1 What is kept as files

**Exercise bank** – `app/math_algebra9.json` (9th grade algebra/geometry):
- `units`: 24 lessons (id, name, month, and for 4 of them a written `quiz` of four questions with points, 45 minutes and the skills each question tests; used as assignable material, QZ-6).
- `skills`: 96 skills (id, lesson, name, short name, description, prerequisites, month, `questions`).
- `questions`: 1,050 multiple-choice questions, 410 with a geometry figure and 53 with a graph. Each wrong choice has a `mistake` id. One skill (`a_30_side`) has no multiple-choice question, only an open-ended `sample` question.
- `mistakes`: 244 mistakes, each with a name and a tip; 40 also name a skill to go back to (`back`).

**Smart board** – `static/math-board.js` (the board), `static/board-math.js` (typed math on the board) and
`static/vendor/mathlive/` (the math keyboard library, MIT license, loaded by board-math.js).
It exposes `window.MathlyBoard` and turns a sketch into a picture for handing in.

### 7.2 Behavior to port from mathly1

Rebuilt, not copied as a whole; read the places named in each requirement group. The notes in this document come from reading mathly1's code; the one claim also checked by running it (locally, sign-in off) is that mathly1 has no visible photo-help entry.

| Area | Where in mathly1 |
|---|---|
| Sign-in page and session | `static/index.html`, `static/math.js` `boot()` |
| Roles and permissions | `app/access.py`, `app/auth.py` |
| Classes | `static/math.js` `manageClasses`…, `app/main.py` `/api/classes` |
| The path, stars, fading, comets | `static/math.js` `pathView`, `orbitRing`; `static/math-sky.js`; `static/math.css` |
| Exercise screen | `static/math.js` `open`, `answer`, `choiceButtons`, `figures` (geometry figures and graphs) |
| Handwritten answers and phone photos | `static/answer-scans.js`, `app/answer_scans.py`, `app/answer_routes.py`, `app/push.py`, `static/service-worker.js` |
| The AI | `app/math_photo.py`, `app/answer_grading.py`, `app/ai_queue.py`, `app/ai_batches.py`, `app/teacher_ai.py`, `app/ai_usage.py`, `app/teacher_review.py`, `app/teacher_inbox.py` |
| Prompter | `app/prompter.py`, `static/prompter.js` |

### 7.3 Notes for the build

- **Stack and hosting.** FastAPI (Python), Supabase (sign-in and storage), plain JavaScript modules in the browser, one Docker container run as a **Hugging Face Space**, replacing mathly1's.
  Settings come from, in order, real environment variables, the app's own `.env` if it has one, and the repository's `.env` (the one mathly1 uses, with the same keys); earlier sources win. With Supabase unset, local development uses an in-memory store and a "dev only" email sign-in, and a half-configured server refuses to start.
  The app page and its styles and scripts are sent with `Cache-Control: no-cache`, so after an update every device gets the new version without clearing its cache (an unchanged file is still answered from the cache). The page declares mathly1's icon (`static/icons/`), shown in the browser tab.
  The server reads the same fact once per request, makes independent database reads at the same time, and reuses its connections: a student's screen waits for the database at most 3 times in a row and a practice answer at most 4 (each call to a remote database costs about 0.4 seconds).
  The server remembers the classes, their students, the roles, the tests and the assignments for at most 30 seconds (`MATHLY_CACHE_SECONDS`, 0 turns it off) and forgets them at once when the app changes one; a screen opened again shows what it last knew and refreshes it, without redrawing over something being typed. One server process is assumed.
  Further settings: the AI key and model (`ANTHROPIC_API_KEY`, `MATH_MODEL`), the push keys (`VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`), the private bucket for answer pictures, and the teacher and developer email lists.
- **Server decides.** Correctness of answers, the date of each answer, mastery, grades, the budgets, and the simulation and exercise-test timers are decided and stored on the server.
  Grades that matter cannot be changed from the device.
- **Content gaps in the bank.** The app needs content the bank does not have yet:
  - nothing for lesson quizzes: they are drawn from the existing questions (QZ-2);
  - one skill has no multiple-choice question;
  - a **solved example for the help button: none of the 96 skills has one** (every skill has an explanation; the single `sample` is an open question);
  - a skill to go back to for 204 of the 244 mistakes;
  - enough questions per skill for "a different question" and for retakes that draw new questions.
  A drafting tool can write solved examples with AI for a teacher to approve.
- **Database problems.** When the database cannot be reached, or refuses a request that is not a conflict the person caused, the person sees a message saying so, with a hint that migrations may be missing, and the reason goes to the server log. It is never reported as a different problem, such as a name already in use.
- **Start empty.** The app starts with no students, classes or progress; nothing is imported from mathly1.
- **Fallback to mathly1.** mathly1's database must keep working untouched, so the Space can be switched back to mathly1 and its students find their data as they left it.
  The app therefore only **adds** its own tables (named with an `m2_` prefix, as the migrations do) and never changes, empties or deletes any table, policy or storage bucket that mathly1 uses.
  Sign-in accounts are the Supabase project's, so the same Google accounts work in both. mathly1's code stays in the repository (tagged) so its image can be redeployed.
  mathly2 uses mathly1's Supabase project, with the `m2_` tables beside the old ones. Before the Space is switched, mathly1's own uncommitted work is committed and tagged so the fallback is exactly what ran before.

## 8. Success Metrics

- ≥ 90% of students take the simulation test before each real test.
- On test day, students have mastered on average ≥ 80% of the covered skills.
- ≥ 75% of students take both exercise tests before each real test.
- Teachers open the progress view at least once a week.
- The AI's estimated cost stays within each class's daily budget on every day.

## 9. Open Questions

None. Every question raised so far is decided below; new ones are added here as they come up.

### Decisions already taken

- Math only. The app starts empty (no data import). Google sign-in.
- A real test defaults to 12 questions and 45 minutes. The calculator is allowed in quizzes, exercise tests and the simulation.
- A class's teacher adds and removes the students of their own class; managers do everything else about classes.
- The developer lab starts empty.
- The app runs as a Hugging Face Space, replacing mathly1. **mathly1's database is kept unchanged** so the Space can be switched back to mathly1 at any time (see 7.3, Fallback).
  mathly2 uses mathly1's Supabase project, with its own `m2_` tables beside the old ones.
- Lesson quizzes are 10 multiple-choice questions drawn from the bank, 15 minutes, 0–100; the four authored written quizzes become assignable material.
- Readiness is one 0–100 number from mastery (50), exercise tests (20) and the simulation (30), capped at 80 until the simulation is taken.
- Photo help has two entries (exercise screen and home), is routed to a teacher the student chooses when they are in several classes, and works only in classes where a manager has switched the AI on.
- Roles are keyed by email, so an admin can give a role before the person's first sign-in. The Hebrew role names are מנהל כיתות (manager) and מנהל הרשאות (admin).
- The first comet arrives with the first daily goal reached.
- Answer pictures are kept until 31 August of the school year; no names or emails are sent to the AI.
- A class's teacher is never also one of its students: a refused save says why, in view, and keeps what was typed.
- Settings are read from the environment, then `mathly2/.env`, then the repository's `.env`.
- Five roles: student, teacher, manager (creates classes), admin (gives roles to accounts, sees no learning data), developer (everything and the developer tools).
- Mastery is the 3-correct-on-2-days rule with no decay; fading stars are only a visual review cue; the worked-example and faded-example stages are not part of the app.
- The AI is always reached through the teacher; a class has a daily budget.
- Stack: FastAPI + Supabase + plain JavaScript, in this repository, new folder.

## Appendix A. OpenSpec changes and capabilities

The OpenSpec plan in `openspec/changes/` follows this table: one change per stage, built and archived in order. Each capability belongs to exactly one change.
Screens for the student, teacher and manager: `docs/mockups/mathly2-screens.html`.

| Stage | Change | Capabilities | Requirements |
|---|---|---|---|
| 1 | `rebuild-foundation` | `app-basics`, `accounts-and-classes`, `exercise-bank` (existing, modified) | 6 and 7.3 (look, server decisions, fallback), ACC, ADM, CLS, MGR, TCH-1, TCH-9, BNK |
| 2 | `add-learning-core` | `skill-mastery`, `exercise-screen`, `learning-path`, `smart-board` | MST-1 – MST-5, EXR, PTH (without the quiz node and the daily goal), BRD |
| 3 | `add-rewards` | `rewards` | MST-6 – MST-8, CMT, PTH-6 |
| 4 | `add-lesson-quizzes` | `lesson-quizzes`, `grades` | QZ, GRD, STU-3 |
| 5 | `add-test-readiness` | `real-tests`, `test-countdown`, `exercise-tests`, `simulation-test`, `readiness-meter`, `student-home` | TST, TCH-6, EXT, SIM, RDY, STU-1 |
| 6 | `add-written-work` | `written-answers`, `assignments` | ANS, PSH, TCH-2 – TCH-4, STU-5, QZ-6 |
| 7 | `add-ai-help` | `ai-help` | AI, STU-6, TCH-5 |
| 8 | `add-class-progress-views` | `class-progress-views` | TCH-7, TCH-8 |
| 9 | `add-developer-tools` | `developer-tools` | DEV-1 – DEV-4 |
| 10 | `launch-on-space` | none (operations only) | 7.3 Fallback |
