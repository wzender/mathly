# Proposal

## Why

Three things from using the app:
- The teacher's tabs give no sense of how much is in each: how many classes, tests, assignments, and how many submissions wait.
- The student's home has become crowded (other tests, all assignments, a notifications card). It should show only what is critical.
- A slow action (a hand-in, a grade, a save) gives no sign that it is working, so people press again or think it failed.

## What Changes

- **Teacher tabs show a count** next to each name: classes taught, tests, assignments, and submissions waiting in the inbox.
- **Student home shows only the critical things:** the nearest test with its readiness and today's task, a required simulation, the new assignments (not handed in yet), and "continue the path". The other tests are reached from the test's card; the notifications switch moves to the new tab below.
- **A new student tab "הגשות"** lists every assignment from the teachers, grouped by state: new, sent back for correction, handed in and waiting for a check, and checked. The tab bar becomes: בית, מסלול, הגשות, ציונים, האוסף.
- **Any button whose action takes time shows it**, everywhere in the app: after about a third of a second the button shows a spinner and ignores a second press until the action ends (with reduced motion: "…").
- The assignments requirements ("My assignments", and the new "Submissions tab") are written into the stage-6 change `add-written-work`, whose delta is not archived yet; the tasks for them are here.

## Capabilities

### New Capabilities

### Modified Capabilities
- `student-home`: the tab bar gains "הגשות"; home shows only what is critical.
- `accounts-and-classes`: the teacher's tabs show counts.
- `app-basics`: a button that takes time shows it.

## Impact

- `mathly2/static` (the tab bars, home, a new submissions screen, a busy-button hook used by every request), `mathly2/teacher.js`, and one new teacher route for the counts. No database change. PRD STU-1, STU-5, a new STU-7, TCH-1 and the design notes.
