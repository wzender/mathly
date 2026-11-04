# Design

## Context

- Skills live in `app/math_algebra9.json` (96 skills with `id, unit, name, short, description, questions[...]`). Each wrong choice carries a `mistake` key into `mistakes` (`name`, `tip`, `back`). `answer()` in `static/math.js` shows the tip and, through `back`, the skill to strengthen.
- A wrong answer already sets `FIRST=false` and resets the first-try run, so finishing and gold already need clean answers after a mistake.
- Resources (`app/unit_resources.py`, table `math_unit_resources`, private bucket `mathly-resources`): teacher-role only (`students.view`), per unit, optional `skill_id`. They are not per class: every teacher sees every unit's resources.
- A student's open units come from their classes (`MY_CLASSES[].lessons`, enforced on the server by `access_for`).

## Goals / Non-Goals

**Goals:**
- Help at the moment of being stuck, without giving the current answer away.
- Teacher explanations reach students with one checkbox.

**Non-Goals:**
- AI-generated hints at runtime (students never call the AI, by product decision).
- Per-class resources (resources stay per unit, as today).
- Hints for unit-quiz or open questions.

## Decisions

**Static worked examples in the data file, not AI at runtime.** One example per skill keeps the "students never call the AI" rule, costs nothing per use, and can be checked by a teacher. Format: `example: {question, steps: [{do, why}], answer}`, using the same `$…$` math markup as questions. Authoring: a one-off script may draft examples with Claude from each skill's description and questions. A math teacher reviews every example before it is merged. Skills without an example after review simply don't offer one (the validator requires the example to be well-formed when present; a separate test lists skills still missing one, so coverage is visible without blocking the release).

**Offer after the second mistake in the round.** It is counted from the round's wrong answers (`P.missed[id]` size, plus this session's wrong answers). The first mistake is often a slip, and the tip already handles it. Two mistakes suggest a gap in the method. The help "?" stays available at any time, so a student who knows they don't know isn't forced to fail twice.

**Visibility column.** `alter table math_unit_resources add column visible boolean not null default false`. Existing rows stay hidden, which is the safe default because exercises may be test material. The upload form posts `visible`, and its default in the UI depends on the kind. `PATCH /api/math/resources/{rid}` `{visible}` uses the same owner-or-manager rule as delete.

**Student read routes.** `GET /api/math/units/{unit_id}/student-resources` and `GET /api/math/student-resources/{rid}/image`. Both check that the unit is open to the student (the same check that gates the skills API) and `visible = true`. A hidden or foreign resource answers 404, so ids cannot be probed. Images are served with `Cache-Control: private, max-age=300`.

**Recording use.** `P.examples[id] = {n, last}` merged across devices by `mergeProgress` (`n`: most, `last`: latest). `report_part` passes `examples`.

## Risks / Trade-offs

- [Example quality: a wrong worked example teaches a wrong method] → Every example is reviewed by a math teacher before merge. `tests/test_math_skills.py` checks the format only.
- [Students open the example instead of thinking] → It is offered only after two mistakes, and opening it does not help finish or gold, which still need clean first-try answers.
- [A teacher marks an exercise that will be on a test as visible] → Exercises default to hidden, and the checkbox says "גלוי לתלמידים" explicitly.

## Migration Plan

1. Apply the additive migration (one column, default false).
2. Deploy. Without the column, the student resource routes return an empty list and the upload ignores `visible`.
3. Rollback: previous code. The column can stay.
