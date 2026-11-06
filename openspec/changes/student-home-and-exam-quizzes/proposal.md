# Proposal

## Why

The student home screen stacks about ten cards (tasks, comments, assignments, daily goal, review, mistake patterns, exam countdown, practice exam) above the learning path, so a student can't see what matters today. The app also uses "quiz" and "exam" inconsistently ("בוחן סופי", "בוחן תרגול", "מבחן תרגול"). And before a school exam, it offers one generic practice exam instead of practice matched to each student. The November Grade 9 exam (15–16.11.2026) is the first real case.

## What Changes

**Terms (shown to students and teachers, in Hebrew)**
- **בוחן (quiz):** can be retaken, the best grade counts, chosen for each student.
- **מבחן (exam):** handed in once.
- The practice unit-quiz sitting is shown as a בוחן, the final unit-quiz sitting as a מבחן, and the mixed "מבחן תרגול" becomes a בוחן. Server names (`mode: practice|final`) do not change.
- For a practice unit quiz, the best grade is the one shown as its grade; the latest stays visible. The official grade of a unit is still the latest final sitting.

**Home and path**
- The student's **בית** (home) tab shows only things that have a date or need action:
  - the next exam on the class exam table (countdown, link to its preparation)
  - up to 3 quizzes
  - work that is due
  - new teacher comments
  - a "continue the path" button, so home is never empty
- A new **מסלול** (path) tab holds the trail of units and topics, the daily goal, spaced review and the recurring-mistakes card.
- A teacher's home (their classes) does not change.

**Three quizzes before an exam**
- When an exam that names units is 7 days away or less, the student gets three quizzes of 12 multiple-choice questions:
  1. **בוחן חיזוק**: topics chosen so the student is expected to get about 70% right, mostly topics they are close to mastering.
  2. **בוחן חיזוק**: about 80% expected, with more topics they already know.
  3. **בוחן כמו במבחן**: only the exam's units, mixed, with topic names hidden.
- Quizzes 1–2 give feedback after each answer, with the worked example after a wrong one.
- Quiz 3 gives feedback only at the end, with at most 3 things to fix. It also has an optional "how sure are you?" per answer and a one-line reflection.
- Every retake draws new questions, and the best grade counts.
- Recommended days before the exam: quiz 1 at 7–4, quiz 2 at 5–3, quiz 3 at 3–2. Home marks the one recommended for today.
- With no exam in the next 7 days, home offers the two strengthening quizzes over the units taught so far.
- Wording on screen never says "weakness". Results are compared only with the student's own earlier attempts.
- Topics a student has not started are not quizzed; they stay in the preparation plan as "to learn". A topic with fewer than 5 answers falls back to the topics taught most recently.
- The exam preparation plan's last step ("מבחן תרגול על החומר") becomes the three quizzes.

Nothing here is **BREAKING** for stored data: existing practice-exam results (`P.quizzes`) stay and are shown as earlier quizzes.

## Capabilities

### New Capabilities
- `student-home`: what the student's home tab and path tab each show, their order and the empty state.
- `exam-quizzes`: the three quizzes before an exam (and the two without one): how questions are chosen for each student, feedback, retakes with new questions, best grade, recommended days, confidence and reflection.
- `assessment-terms`: the בוחן / מבחן names across student and teacher screens, and which grade a quiz shows.

### Modified Capabilities
None under `openspec/specs/` (the main specs directory is empty). This change builds on capabilities still held in the unarchived `improve-student-teacher-loop` change: `exam-preparation` (the plan's last step is replaced by the three quizzes), `unit-quiz-modes` and `student-gradebook` (names and the best grade shown for practice), and `student-task-hub` (its home summary now sits on the new home). See design.md, "Relation to in-flight changes".

## Impact

- **Front end**: `static/math.js` (tabs and views, `pathView` split into home and path, the practice exam in `quizSetup`/`quizStart`/`quizSubmit` becomes the quiz engine, prep-plan steps, labels), `static/math-sky.js` (a per-topic expected-success estimate next to `Sky.focus`), `static/math.css` (home layout, quiz cards), `static/guide.js` (student and teacher guide).
- **Server**: no new routes or tables. Quiz results stay in the student's synced progress (`P.quizzes`, merged in `mergeProgress`).
- **Content**: none required. Topics with few questions limit how many retakes can be fully new (see design).
- **Tests**: `tests/test_sky_browser.py` (estimate and question choice), `tests/test_exam_prep_browser.py`, a new Playwright flow for home and path, and existing browser tests that open the home screen.
