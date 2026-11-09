# Proposal

## Why

Choosing the lessons of each class is a chore nobody needs: every class studies the whole bank, as one course. The course should have a name students recognise: "מתמטיקה כיתה ט - מצוינות".

## What Changes

- **A class no longer has chosen lessons.** Every class studies every lesson of the bank. The class form has no lesson list, and class lists do not show lessons.
- **A student in any class sees every lesson** (the path, the skills, the collection).
- **The subject card is named "מתמטיקה כיתה ט - מצוינות"** (the course name), instead of "מתמטיקה".
- A test still covers the lessons the teacher picks for it (unchanged).
- Classes saved earlier with some lessons are treated the same: the stored list is no longer used to limit anything. No database change.

## Capabilities

### Modified Capabilities
- `accounts-and-classes`: classes have no chosen lessons; a student's lessons are all of them.
- `learning-path`: the subject card carries the course name.

## Impact

- `classes.py` (no lessons in the body; the stored list is all lessons), `skills.py` and `main.py` (visibility), `manager.js`, `path.js`. PRD sections on classes and the subject card.
