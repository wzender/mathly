# Proposal

## Why

Every wrong choice in the math path is already tagged with a named misconception (244 of them, e.g. `sign_mid`, `ext_partial`), but the tag is used only for the immediate tip and then forgotten: a wrong answer records nothing but a reset run. So the app cannot see that a student keeps making the same mistake across different skills, which is the weakness that actually blocks understanding. Remembering these tags is also the foundation for a later personal path that mixes weak and strong skills.

## What Changes

- Record every wrong answer's misconception, with its skill, question, date and where it happened (skill practice, mixed review, practice exam), in the student's progress on the device.
- Add a "patterns that come back" (דפוסים שחוזרים) card on the math home screen when a misconception has come up at least twice recently, naming the misconception and in how many skills it appears.
- Opening the card shows up to three recurring misconceptions, each with its tip, how often and how recently it came up, and buttons to practise the skill to strengthen.
- The patterns also show where the student already looks: the skill to strengthen is marked "לחזק" on the path, and a mistake that is now a pattern says so in its feedback, with the skill to strengthen.
- A pattern that has not come up again for a while leaves the list, and the card says when a pattern used to recur and has stopped ("נעלם"), so improvement is visible.
- Wording stays about the mistake, never about the student, matching the existing quiet-mistake tone.
- Unit-quiz (photographed, open-ended) answers have no misconception tags and are not included.
- Nothing is sent to the server; progress stays in localStorage as today. Existing progress without the new log keeps working.

## Capabilities

### New Capabilities

- `misconception-patterns`: recording a student's tagged mistakes across all multiple-choice practice and showing them the misconceptions that recur across skills, with what to practise.

### Modified Capabilities

(none: there are no main specs yet; skill practice, review and the practice exam keep their current behaviour and only also record the mistake)

## Impact

- `static/math-sky.js`: progress shape gains a mistake log, and functions to add to it and to summarise it.
- `static/math.js`: wrong answers in practice (`answer`), review (`reviewAnswer`) and the practice exam (`quizSubmit`) log the mistake; new home card and sheet.
- `static/math.css`: styles for the card and sheet.
- `tests/test_sky_browser.py`: browser tests for logging and the card.
- No server, API or data-file changes.
