# Tasks

## 1. Bank: question keys and example content

- [ ] 1.1 Add `question_key(skill_id, question)` to `bank.py` (design decision 3) and make `check_bank` reject two questions with the same key in a skill; verify tests pass on the real bank and fail on a sample with a duplicated question
- [ ] 1.2 Add checks for the optional `worked_example` and `faded_examples` shapes (decision 4: exactly 2 faded examples with at least 2 and 3 steps, one correct `why` and one correct choice per step, mistake ids exist); verify tests pass on a valid sample and fail on each broken case, and the real bank (with no examples) still loads
- [ ] 1.3 Add `Bank` helpers for practice: a question for the browser without `correct` or `mistake` (choices keep their original index), grading a choice index, and a mistake's name, tip and `back`; verify unit tests, including that a served question has no `correct` field anywhere
- [ ] 1.4 Update `scripts/content_gaps.py` to the decision 4 shape (a step without `why` choices, a faded step without choices); verify its test still lists `a_30_side` and flags a sample step without choices

## 2. Storage

- [ ] 2.1 Add the migration `mathly2/supabase/migrations/…_m2_skill_learning.sql` with `m2_answers`, `m2_skill_progress` and the `m2_daily_correct` view (decision 1), row-level security on and no browser grants; verify a pgserver test applies it, the view counts only correct practice answers per day, and an authenticated-role insert is refused
- [ ] 2.2 Add the progress and answer methods to `InMemoryStore` (get or create progress, update progress, insert answer, last N counted answers, answer counts per question, daily correct counts, progress rows of a user); verify unit tests for each method
- [ ] 2.3 Add the same methods to `SupabaseStore`; verify `test_store.py`-style tests against the faked PostgREST pass with the same cases as 2.2

## 3. Rules: mastery, next question, goal and streak

- [ ] 3.1 Add `learning.py` with the mastery rule over counted answers (decision 2); verify a test for every scenario in `specs/skill-mastery/spec.md`: two days, one day, help opened, help between correct answers, streak broken, months later still mastered
- [ ] 3.2 Add the skill state from a progress row (not started, learning, mastered); verify tests that a "why this step?" answer moves a skill to learning and only practice answers can master it
- [ ] 3.3 Add next-question picking (decision 7): fewest past answers, never the one just answered; verify tests with 10 questions (no repeat before all are seen), 1 question (repeats) and 0 questions (none)
- [ ] 3.4 Add today's goal and the streak from daily counts (decision 8), using `clock.school_day()`; verify tests for 3 of 5, reaching 5, a streak kept overnight before today's 5, and a broken streak

## 4. Practice API

- [ ] 4.1 Add `GET /api/skills/{id}` (stage, examples if any, current question) and `POST /api/skills/{id}/stage`; verify tests that a skill with no examples opens at practice, a skill with a worked example but no faded examples moves to practice after it (spec: Stages without content are skipped), and any skill opens in any order (spec: Jumping ahead)
- [ ] 4.2 Add `POST /api/skills/{id}/answer` per the decision 6 sequence; verify tests that the server dates the answer (spec: Device clock changed), a wrong answer returns the mistake's name and tip but not the correct choice, the next question differs from the one answered, and an answer for a question not on screen is refused
- [ ] 4.3 Add `POST /api/skills/{id}/help`; verify a test that the next answer is stored with `counted = false` and does not break a run
- [ ] 4.4 Add `GET /api/path` and `GET /api/collection`; verify tests for states, today's goal, the streak, mastered skills, and a lesson counted as completed only when all its skills are mastered
- [ ] 4.5 Extend the "no content before sign-in" test to the new endpoints, and refuse a student with no class (403) as `/api/lessons` does; verify the test passes

## 5. Student screens

- [ ] 5.1 Port the `figure` and `plot` drawing functions from the old `static/math.js` into `mathly2/static/figures.js` (decision 9); verify a Playwright test draws one bank question with a `figure` and one with a `graph`
- [ ] 5.2 Replace the lesson list in `student.js` with the path screen: every lesson and skill with its state as text and symbol, today's goal and the streak; verify a Playwright test at 390px shows all 24 lessons, a mastered skill's label, and no horizontal scroll
- [ ] 5.3 Add the worked-example screen: one step at a time, the next step only after "why this step?" is answered; verify a Playwright test against a test bank with one worked example
- [ ] 5.4 Add the faded-example screen with backward fading and mistake feedback on a wrong step; verify a Playwright test that example 1 hides one step, example 2 hides two, and a wrong choice shows its mistake
- [ ] 5.5 Add the practice screen: choices, help, mistake feedback with a "similar question" button and a "go back to" link when the mistake has `back`, and the run of correct answers; verify a Playwright test that answers wrongly, sees the mistake name, and gets a different question
- [ ] 5.6 Add the collection screen; verify a Playwright test that a skill mastered through the API appears on it

## 6. Drafting tool

- [ ] 6.1 Port `scripts/draft_examples.py` to `mathly2/scripts/draft_examples.py`, producing the decision 4 shape (one worked example and 2 faded examples per skill) and merging only approved drafts through `check_bank`; verify tests with a faked AI client for draft, a rejected draft, and merge, and `--dry-run` sends nothing
- [ ] 6.2 Document the draft -> teacher approves -> merge flow in `mathly2/README.md`; verify the documented `--dry-run` command runs as written

## 7. Integration

- [ ] 7.1 Walk one skill end to end in a browser test: open from the path, answer 2 correctly, move the server clock to the next day, answer 1 more, and see the skill as mastered on the path and in the collection; verify the test passes
- [ ] 7.2 Run the whole suite `venv/bin/python -m pytest mathly2/tests` and `openspec validate build-skill-learning`; verify both pass

## Workflow follow-up

- Write worked and faded examples for a first lesson with the drafting tool and have a teacher approve them (content work, outside this change).
- Archive this change once it is deployed and reviewed, so `skill-learning`, `skill-mastery` and `learning-path` move into `openspec/specs/`.
