# Tasks

## 1. Worked example content

- [x] 1.1 Add `example` validation to `app/math_skills.py` (own question, at least one step with `do`/`why`, `answer`) and send it in the skills API. Verify in `tests/test_math_skills.py` with a valid example and one that copies a practice question.
- [x] 1.2 Write a one-off drafting script under `scripts/` that proposes examples for skills without one, writing to a review file, not to the data file. Verify it runs on one unit and produces well-formed drafts.
- [ ] 1.3 Add reviewed examples to `app/math_algebra9.json`, unit by unit, each one approved by a math teacher. Verify the validation test passes and the coverage test lists the skills still missing one.

## 2. Help in practice

- [x] 2.1 In `static/math.js`, offer "איך פותרים? דוגמה פתורה" from the second wrong answer in the round, and show the example inside the sheet with a return to the same question. Verify with a browser test: no offer after one mistake, offer after two, same question after closing.
- [x] 2.2 Add the "?" help panel in the skill sheet (description, example, teacher explanations for the skill). Verify in the browser test.
- [x] 2.3 Record `P.examples[id]` (count and last) and merge it across devices in `mergeProgress`. Add it to `ensure` in `static/math-sky.js`. Verify with a browser test that finishing and gold are unchanged by opening the example, and with a merge test.

## 3. Resource visibility

- [x] 3.1 Add migration `<ts>_math_resources_visible.sql` (column `visible` default false). Verify it applies on the test database.
- [x] 3.2 In `app/unit_resources.py`, accept `visible` on upload and add `PATCH /api/math/resources/{rid}` with the owner-or-manager rule. Verify in `tests/test_unit_resources.py`: defaults by kind, owner can toggle, another teacher gets 403.
- [x] 3.3 Add the student routes (list and image) limited to visible resources of the student's open units, answering 404 otherwise. Verify the tests: hidden resource 404, unit not open 404 or empty, no `object_key` in the response.
- [x] 3.4 In the UI, add the visibility checkbox to the upload form, a toggle and a "visible" mark on each resource for teachers, and the "הסברים מהמורה" lists for students in the skill sheet and unit. Verify with browser tests for both roles.

## 4. Report and docs

- [x] 4.1 Add `examples` to `report_part` and show on the student's card the skills where an example was opened in the last 14 days. Verify in `tests/test_class_report.py` and the report browser test.
- [x] 4.2 Update `static/guide.js` (student: the help and teacher explanations; teacher: visibility of resources, replacing "בשלב זה המשאבים גלויים למורים בלבד") and `README.md`. Verify `tests/test_guide_browser.py` passes.

## 5. Integration

- [x] 5.1 Run the full `pytest` suite and check locally, as a teacher and a student in the same class, that a theory photo uploaded by the teacher appears in the student's skill sheet.
