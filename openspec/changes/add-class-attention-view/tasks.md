# Tasks

## 1. Report data

- [x] 1.1 In `app/class_report.py`, add `seen` and `tries` to `report_part`. Verify in `tests/test_class_report.py` that both are returned and non-object values are dropped.
- [x] 1.2 Return each student's display name (class nickname, else Google full name, else null) from the report, extending `app/auth.py` `user_ids` to collect `user_metadata` names. Verify with a test using a fake admin user list with and without names.

## 2. Needs-attention section

- [x] 2.1 Add the attention constants and a pure `attentionOf(student, units, now)` in `static/math.js` returning a list of reasons. Verify with a browser test (pattern of `tests/test_sky_browser.py`) feeding fixed progress objects for each signal, including the "small numbers are not a drop" case.
- [x] 2.2 Render the "דורשים תשומת לב" section at the top of the report, with the empty-state text, and each student's reasons linking to their card. Verify with a browser test of the report sheet.
- [x] 2.3 Show weekly activity (this week / last week) on each card. Verify in the same browser test with known `days`.

## 3. Grid and sorting

- [x] 3.1 Add list/grid tabs, the unit picker, the per-skill grid using `MathlySky.star` states, the column counts and the class-difficulty mark. Verify with a browser test on a 3-student fixture, checking cell states and the marked column.
- [x] 3.2 Add the units overview. Verify finished/total per unit in the browser test.
- [x] 3.3 Add the sort control (attention, name, progress, last activity), saved in `localStorage` with try/catch. Verify order changes in the browser test.
- [x] 3.4 Use display names everywhere in the report, with the full email kept in the card. Verify in the browser test.
- [x] 3.5 Add CSS for the grid with a sticky name column and sideways scrolling inside its box. Verify at 375 px width in Playwright that the page itself has no horizontal scroll.

## 4. Docs and integration

- [x] 4.1 Update the "דוח הכיתה" section of the teacher tab in `static/guide.js` and the class-teacher section of `README.md`. Verify `tests/test_guide_browser.py` passes.
- [ ] 4.2 Run the full `pytest` suite and open the report for a real class locally to check the attention list against the cards.
