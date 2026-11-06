# Design

## Context

See proposal.md for the motivation. The current code that shapes the approach:

- **One view for home and path.** `pathView()` in `static/math.js` returns every card and the trail in one string: `topBar`, `classesCard`, `tasksSummary`, `commentsCard`, `assignmentsCard`, `daily`, `reviewCard`, `patternsCard`, `examSoon`, `quizCard`, then the trail. `TABS` has `path` (labelled "בית") and `sky` ("האוסף"); `VIEW` starts as `"path"`. For a class teacher not in preview, `pathView` returns only `topBar` and `classesCard`.
- **Practice exam.** `quizSetup`/`quizStart`/`quizShow`/`quizSubmit` pick 12 multiple-choice questions from chosen units, give no feedback until hand-in, and push `{at,n,right,ms,units,weak}` to `P.quizzes` (last 20). `mergeProgress` joins `P.quizzes` across devices by `at`.
- **Per-topic data on the device.** `P.tries[id]` counts answers, `P.slips` keeps tagged wrong answers (last 500, with time and question index), `P.done`/`P.gold`/`Sky.fading` give mastery, `P.seen[id]` the last practice. There is no per-topic count of right answers, and untagged wrong answers are not in `P.slips`.
- **Weakness score.** `Sky.focus(P, sittings, ids)` in `static/math-sky.js` ranks topics (quiz points lost, recent wrong answers, unfinished, fading) with weights in `FOCUS`.
- **Exam preparation.** `prepExams`, `prepSteps`, `prepPlan`, `prepDone` and `drawPrep` build the per-exam plan. Its last step `{k:"exam"}` starts the practice exam preset to the exam's units.
- **Labels.** About 49 occurrences of "בוחן סופי", "בוחן תרגול" and "מבחן תרגול" across `static/*.js` and `app/*.py`.

## Goals / Non-Goals

**Goals:**
- Reuse the practice-exam engine for all three quizzes instead of adding a second quiz system.
- Keep everything on the device and in synced progress, as the practice exam is today. No new server routes or tables.
- Keep the expected-success estimate, its weights and the quiz targets in one constant table, tested.

**Non-Goals:**
- Teacher views of the new quizzes, confidence marks or reflections (a later change can add them to the focus profile).
- Open-answer or photo questions in these quizzes. They stay multiple-choice; handwritten work stays in unit quizzes.
- New content. Topics with few questions limit fully fresh retakes (see Risks).
- Changing server field names (`mode: practice|final`) or stored grades.

## Decisions

### D1. Two views from one, chosen by `VIEW`
Split `pathView()` into `homeView()` and `pathView()`.
- `TABS` becomes `home` ("בית"), `path` ("מסלול"), `sky` ("האוסף"), and `VIEW` starts as `"home"`.
- `homeView` renders `topBar`, `classesCard` (only when it asks the student to act), the exam item, the quizzes, `tasksSummary`, `assignmentsCard`, `commentsCard` with only unseen comments, and the "continue the path" button.
- `pathView` keeps `topBar`, `daily`, `reviewCard`, `patternsCard` and the trail.
- `examSoon` and `quizCard` are replaced by the exam item and the quiz cards.
- Links that open the trail (`data-view="path"` from the collection, "continue") keep working because they already name `path`.
- A class teacher outside preview gets `home` showing their classes, and `path` is left out of `TABS`.

*Alternative:* collapse cards on one long screen. Rejected: the screen still opens on the clutter, which is the problem.

### D2. Expected success per topic: `Sky.chance(P, id)`
A small Bayesian estimate:
- wrong = the larger of `P.wrongs[id]` (D6) and the topic's entries in `P.slips`. Every wrong multiple-choice answer carries a mistake tag, so the slips hold the history from before `P.wrongs` existed (up to 500).
- chance = `(tries − wrong + 1) / (tries + 2)`, with wrong capped at tries.
- Adjustments: finished → at least 0.8; gold → at least 0.9; fading → minus 0.1.
- Fewer than 5 answers → "unknown" (`null`).
- Constants live in a `CHANCE` table next to `FOCUS`.

*Alternative:* reuse `Sky.focus` scores. Rejected: a ranking is not a probability, and the quizzes need an expected score.

### D3. Choosing questions for a target: `Sky.pickQuiz(P, ids, {target, n, seen})`
1. Eligible topics are those started (`P.tries` or `P.seen` or `P.missed`). Topics never practised are out.
2. Known topics (chance not `null`) are split into "close" (unfinished, or chance < 0.75) and "solid".
3. Greedy fill: take questions from close topics, at most 3 per topic, rotating so no topic dominates. Add solid topics while the running mean chance is below `target`. Stop at `n`.
4. If fewer than `n`, fill from unknown topics, most recently taught first (by `month`, then `ORDER`).
5. Inside a topic, choose multiple-choice questions not in `seen`. If none remain, choose the one seen longest ago.

Targets are 0.70 (quiz 1) and 0.80 (quiz 2). The function returns the questions and their expected score, which tests check against the spec's bands. It lives in `math-sky.js` so it can be tested without the page.

### D4. One quiz engine with a kind
`QZ` and the stored entries in `P.quizzes` gain:
- `kind` (`s1`, `s2`, `exam`), `exam` (the exam key or `null`) and `qs` (`"id:qi"` keys).
- for the exam-like quiz: `sure` (per-question confidence) and `note` (the reflection).

The engine has two behaviours:
- **Feedback mode (`s1`, `s2`):** a pick is final. It shows right or wrong and the mistake's tip, and after a wrong answer offers the worked example (`exampleCard`), then "next". Skill names stay hidden.
- **Exam mode (`exam`):** the current practice-exam flow, plus a three-button confidence row under the choices and the reflection field on the result.

The exam-like quiz draws questions spread over the exam's units with the current `quizStart` proportions, restricted to started topics and avoiding `seen`.

`P.quizzes` grows from the last 20 entries to the last 60, so a few weeks of three quizzes are kept. `mergeProgress` already joins entries by `at`. The new fields ride along unchanged.

*Alternative:* store quiz attempts on the server. Rejected for now: no grade here is official, and the practice exam already syncs through progress.

### D5. Which quizzes home shows
`homeQuizzes()`:
- When `prepExams()[0]` is 7 days away or less, it returns `s1`, `s2` and `exam` for that exam's units.
- Otherwise it returns `s1` and `s2` over the units taught so far (the current `quizUnits()` rule without an exam).

Each card shows:
- its recommended days and whether it is recommended today (the spec's day bands)
- the best `right/n` over attempts of that kind and exam (or with `exam: null`)
- the change from the previous attempt
- "can't start yet" with the topics to learn when fewer than 6 questions can be drawn

`prepSteps` replaces `{k:"exam"}` with three steps `{k:"quiz", kind}`. `prepDone` checks for an attempt of that kind and exam after the plan was opened. Plans already stored with `{k:"exam"}` are rebuilt once when read (the step list is derived data).

### D6. Small additions to answer recording
- `Sky.wrong` counts every wrong answer in `P.wrongs[id]`, and quiz answers update `P.tries` and `P.wrongs` like practice.
- `mergeProgress` merges `wrongs` with "most", like `tries`.

### D7. Labels in one table
Add one `TERMS` table in `math.js` (`quiz: "בוחן"`, `exam: "מבחן"`, and the full phrases used) and replace the 49 occurrences, the guide texts and the teacher report's tab name ("בחנים סופיים" → "מבחנים"). Python strings seen by users (route error messages shown in the UI) are changed in place. The grades page shows a practice unit quiz's best grade first, then the latest when it differs; the server already returns all sittings, so this is front-end only.

### Relation to in-flight changes
`improve-student-teacher-loop` is implemented but not archived. This change narrows its specs as follows, so its main specs should be synced before this one is archived:
- `exam-preparation` "Student gets a preparation plan": the last step becomes the three quizzes.
- `student-gradebook`: practice shows best first. The words "בוחן סופי" and "תרגול" in its scenarios become "מבחן" and "בוחן".
- `unit-quiz-modes` "Confirmation": the button text becomes "התחלת המבחן".
- `student-task-hub`: the home summary now lives on the new home tab.

At archive time these become MODIFIED deltas against the synced main specs.

## Risks / Trade-offs

- [Topics have about 10 questions each, so fresh retakes run out after 2–3 attempts per topic] → fall back to the questions seen longest ago; the card says when questions start to repeat. More questions can be added to the content later without spec changes.
- [The estimate is rough, especially before `P.wrongs` has data] → targets are bands, not exact; the weights live in one tested table and can be tuned.
- [Students lose the cards they're used to seeing on home] → the tab bar names "מסלול", and the "continue" button leads there; the guide explains the split.
- [Renaming 49 strings breaks browser tests that look for old text] → change tests in the same task as the strings, and add a test that none of the old phrases appear.
- [Confidence and reflection go unused] → both are optional and cheap. Usage can be checked later in synced progress.

## Migration Plan

1. Front-end only; deploy as one release. Existing `P.quizzes` entries without `kind` are shown as earlier general quizzes and do not count toward the exam quizzes.
2. Stored prep plans with the old practice-exam step are rebuilt on first read.
3. Rollback: revert the front end. Extra fields in `P.quizzes` and `P.wrongs` are ignored by old code.
