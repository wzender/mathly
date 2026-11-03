# Tasks

## 1. Mistake log and summary rules (static/math-sky.js)

- [x] 1.1 Make `ensure(P)` create `P.slips` as an array when missing or invalid; verify with a browser test that progress saved without `slips` loads the path without errors
- [x] 1.2 Add `Sky.slip(P,id,q,m,via,now)` that appends `{at,id,q,m,via}` and keeps the newest 500; export it on `window.MathlySky`; verify with a page-evaluated test that 501 calls leave 500 entries with the oldest dropped
- [x] 1.3 Add `Sky.patterns(P,mistakes,now)` returning `{recurring,stopped}` per the spec (2+ in 30 days with 1 in the last 14 → recurring; 2 within some 30-day span, last seen 14–60 days ago → stopped; ranked by skills, count, recency; 3 each; `practise` = back-skill or most frequent skill); verify with page-evaluated tests covering each spec scenario under "Recurring misconceptions are identified" and "Improvement is shown"

## 2. Logging wrong answers (static/math.js)

- [x] 2.1 In `answer()` call `Sky.slip(...,"practice")` on a wrong tagged choice before `save()`; verify a browser test picks a wrong choice in `t_ext` and finds one entry with that tag and `via:"practice"`, and that the existing quiet-mistake test still passes
- [x] 2.2 In `reviewAnswer()` log wrong answers with `"review"`; verify the existing review test still passes and a wrong review answer adds one `review` entry
- [x] 2.3 In `quizSubmit()` log each final wrong pick with `"exam"`; verify a test that changes a pick and hands in logs only final picks, and that quitting an exam logs nothing

## 3. Patterns card and sheet (static/math.js, static/math.css)

- [x] 3.1 Add `patternsCard()` after `reviewCard()` in the home screen, shown only when `Sky.patterns` has a recurring or stopped pattern, with the copy from design.md; verify browser tests with seeded progress: no card when empty, card naming the top misconception and its skill count, card wording for stopped-only
- [x] 3.2 Add the `patterns` sheet (`data-act="patterns"`): up to three recurring entries with name, tip, count, skill count, last-seen day and a "לחזק" button opening the practise skill, then a "דפוסים שנעלמו" section; verify a browser test that the button for a tag with `back` opens that skill and for a tag without `back` opens its most frequent skill
- [x] 3.3 Style the card and sheet to match `mx-review`/`mx-quiz-card` in light and dark, at phone width; verify by screenshot at 375px and that no horizontal scroll appears
- [x] 3.4 Update the header comment of `static/math.js` (progress fields) to describe `slips`; verify by reading the comment

## 4. Patterns where the student looks (path and feedback)

- [x] 4.1 Mark the skills to strengthen on the path (gold ring and "לחזק" tag, "ממשיכים כאן" wins); verify `test_the_path_marks_the_skill_to_strengthen` and a 375px screenshot
- [x] 4.2 Add the pattern note to practice and review feedback, without repeating a button already offered; verify `test_a_mistake_that_is_a_pattern_says_so_where_it_happens` and `test_a_first_mistake_has_no_pattern_note`

## 5. Integration check

- [x] 5.1 Run `pytest tests/test_sky_browser.py tests/test_math_skills.py` and confirm all pass, including the existing practice, review and exam tests unchanged
