# Tasks

## 1. Quiz and exam names

- [x] 1.1 Add a `TERMS` table to `static/math.js` and replace every "בוחן סופי", "בוחן תרגול" and "מבחן תרגול" on student and teacher screens (including the report tab "בחנים סופיים" → "מבחנים" and "התחלת הבוחן הסופי" → "התחלת המבחן"); change the user-visible Python strings in place; verify with a new test in `tests/test_sky_browser.py` that renders the student and teacher screens and finds none of the old phrases
- [x] 1.2 Grades page: a practice unit quiz shows its best grade first, then the latest when different; the official grade stays the latest final sitting; verify both scenarios of "A quiz shows its best grade" in the grades-page Playwright flow
- [x] 1.3 Update the existing browser tests that look for the old phrases (`tests/test_unit_quiz.py`, `tests/test_loop_browser.py`, `tests/test_exam_prep_browser.py` and others found by grep); verify `pytest tests -k browser` passes
- [x] 1.4 Update `static/guide.js` (student and teacher) with the בוחן / מבחן definitions; verify `tests/test_guide_browser.py` passes and the guide shows both terms

## 2. Home and path tabs

- [x] 2.1 Split `pathView()` into `homeView()` and `pathView()`, set `TABS` to בית / מסלול / האוסף, start on `home`, and leave `path` out of `TABS` for a class teacher outside preview; verify with a Playwright flow that the student opens on home, sees no trail there, and the teacher sees their classes with no "מסלול" tab
- [x] 2.2 Home content in order: the next-exam item (subject, date, days left; opens the prep view when the exam names units), the quiz cards (placeholder until group 4), due work (`tasksSummary`, `assignmentsCard`), and only unseen teacher comments; verify the "Busy week" and "Comments already seen" scenarios in the same flow
- [x] 2.3 "Continue the path" button and the empty state; the button opens the path tab scrolled to the next topic; verify both "Home is never empty" scenarios
- [x] 2.4 Path tab: daily goal, review, recurring mistakes, then the trail; collection links still jump to a unit; verify "Review due" and "Jump to a unit"
- [x] 2.5 Fix the existing browser tests that expect cards or the trail on the first screen (`tests/test_sky_browser.py`, `tests/test_focus_browser.py`, `tests/test_loop_browser.py` and others); verify the full browser suite passes
- [x] 2.6 Explain the home and path tabs in the student guide; verify the guide test passes

## 3. Expected success and question choice

- [x] 3.1 Record every wrong answer in `P.wrongs[id]` and merge it with "most" in `mergeProgress`; verify with a merge case in `tests/test_sky_browser.py`
- [x] 3.2 `Sky.chance(P, id)` with the `CHANCE` constants table (unknown under 5 answers, gold/finished/fading adjustments); verify with unit cases for each rule
- [x] 3.3 `Sky.pickQuiz(P, ids, {target, n, seen})` (started topics only, close before solid, at most 3 per topic, unknown topics most-recent-first, unseen questions first, oldest-seen fallback); verify with unit cases: expected score within 65–75% for target 0.70 and 75–85% for 0.80, no unstarted topic, the cold-start fallback, and no repeat while unseen questions remain

## 4. The three quizzes

- [x] 4.1 Extend the quiz engine with `kind`, `exam` and `qs`; raise `P.quizzes` to the last 60; verify an attempt is stored with its kind and questions and survives `mergeProgress`
- [x] 4.2 Feedback mode for `s1`/`s2`: a final pick, right/wrong with the mistake's tip, the worked example after a wrong answer, then next; verify the "Wrong answer" scenario with a Playwright flow
- [x] 4.3 Exam-like mode: exam units only, topic names hidden, no feedback until hand-in, result with per-unit score and at most 3 things to fix; verify the "Handing in" scenario
- [x] 4.4 Optional confidence row per question and the reflection field (≤140 characters) on the exam-like result; list "sure but wrong"; verify "Sure but wrong" and "Skipping both"
- [x] 4.5 `homeQuizzes()`: three quizzes when an exam naming units is ≤7 days away, otherwise two over the units taught so far; recommended-day bands and "מומלץ להיום"; best grade and change from the previous attempt; the "can't start yet" state with topics to learn (fewer than 6 questions); verify "Exam in 6 days", "Exam in 10 days", "Quiet week", "Three days before", "Improvement", "Lower retake" and "Too little practised" with a fixed clock
- [x] 4.6 Replace the old practice-exam card and setup entry points with the new quizzes (the assignment `exam` item still opens a quiz preset to its units); verify an existing practice-exam assignment still opens and counts as done
- [x] 4.7 Wording check: names, descriptions and results never use "חולשה" or "חלש"; verify with a test over the rendered quiz cards and results
- [x] 4.8 Explain the three quizzes, retakes and best grade in the student guide; verify the guide test passes

## 5. Preparation plan

- [x] 5.1 `prepSteps` ends with the three quiz steps instead of the practice exam, `prepDone` checks attempts of that kind and exam after the plan opened, and stored plans with the old step are rebuilt once; verify "Plan steps" and "Step done" in `tests/test_exam_prep_browser.py`
- [x] 5.2 Unstarted topics of the exam's units appear as "to learn" steps and are not quizzed; verify the "Not started yet" scenario

## 6. Integration checks

- [x] 6.1 End-to-end Playwright scenario with a fixed date 6 days before an exam naming `t`, `t2`, `k`, `l`, `o`: the student opens home → sees the exam and three quizzes → takes quiz 1 with feedback → retakes it with new questions → takes the exam-like quiz with confidence marks → the prep plan shows the quiz steps done → the path tab still shows review and the trail
- [ ] 6.2 Run the full test suite (`pytest`) and `openspec validate student-home-and-exam-quizzes --strict`; both pass

## Workflow follow-up

- Sync the specs of `improve-student-teacher-loop` into `openspec/specs/` (archive it) before archiving this change, then turn the narrowed requirements listed in design.md ("Relation to in-flight changes") into MODIFIED deltas.
