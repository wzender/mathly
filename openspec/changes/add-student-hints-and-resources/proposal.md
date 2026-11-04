# Proposal

## Why

When a student picks a wrong answer they see the misconception's name and a one-line tip, and the question comes back later without its answer. That works for a slip, but a student who does not know the method has no way to learn it inside the app. They guess until a question comes back, or give up. Meanwhile teachers photograph explanations from the board into the lesson resources, and those photos are hidden from students ("בשלב זה המשאבים גלויים למורים בלבד"). The help exists, but students cannot reach it.

## What Changes

- Add a **worked example** to skills in `app/math_algebra9.json`: a question similar to the skill's questions (not one of them), solved step by step with a short explanation per step. Examples are written for all 96 skills, drafted with help and checked by a math teacher before release.
- In skill practice, after a **second wrong answer in the same skill in the current round**, the feedback offers **"איך פותרים? דוגמה פתורה"**. It opens the worked example in the sheet without leaving the question. The skill's description and the example are also available any time from a small "?" in the skill sheet's header.
- Using the example is recorded per skill (`P.examples[id]`: how many times and when). The student keeps the same rules for finishing a skill and for gold (the earlier wrong answer already broke the first-try run).
- Teachers can mark a lesson resource **"גלוי לתלמידים"**. When they upload, the box is checked by default for a theory explanation and unchecked for an exercise or other photo. They can change it later on existing resources.
- Students see the visible resources of their class's units:
  - in a skill's sheet, under "הסברים מהמורה", the visible resources tagged with that skill,
  - in the "?" help panel of the skill,
  - in a unit-level "הסברים מהמורה" list for visible resources without a skill tag.
- The class report's student card shows the skills where the student opened the worked example, so the teacher sees where they needed help.

## Capabilities

### New Capabilities

- `practice-help`: help a student can reach while practising a skill: the worked example, when it is offered, and recording its use.
- `lesson-resources`: teacher-uploaded lesson photos, who can see them, and the teacher's control over showing them to students.

### Modified Capabilities

(none: there are no main specs yet)

## Impact

- `app/math_algebra9.json`: an `example` field per skill (`{question, steps:[{do, why}], answer}`). `app/math_skills.py` validates it, and the skills API sends it.
- New migration `<ts>_math_resources_visible.sql`: column `visible boolean not null default false` on `math_unit_resources`.
- `app/unit_resources.py`: a `visible` form field and a toggle route for teachers. Read routes for students, limited to visible resources of their class's units.
- `static/math.js`: the offer after the second wrong answer, the "?" help panel, "הסברים מהמורה" lists, the visibility checkbox and toggle, the report card line. `static/math-sky.js`: `examples` in `ensure` and in the progress merge.
- `app/class_report.py`: `report_part` adds `examples`.
- `static/guide.js` both tabs, `README.md` lesson-resources section.
- Tests: `tests/test_math_skills.py`, `tests/test_unit_resources.py`, `tests/test_sky_browser.py`.
