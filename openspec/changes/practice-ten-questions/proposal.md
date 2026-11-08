# Proposal

## Why

Five skills (`t_ext`, `t_simplify`, `t_ext_eq`, `t_area`, `t_formulas`) have 30 questions in the bank, so their exercise screen says "question n of 30" while every other skill says "of 10". Practice should look the same for every skill.

## What Changes

- Practice on the exercise screen uses 10 questions per skill: the first 10 of the skill's questions in the bank. The count "question n of N", the dots, the progress and the next question all use those 10.
- The bank is untouched: the other questions of those five skills stay, and lesson quizzes, exercise tests and the simulation still draw from all of a skill's questions, so retakes keep their variety.

## Capabilities

### New Capabilities

### Modified Capabilities
- `exercise-screen`: "One question at a time" counts the skill's practice questions, at most 10.

## Impact

- `mathly2/bank.py` (the practice set) and `mathly2/skills.py` (practice uses it); quizzes and tests are unchanged.
- PRD EXR-2 and a new BNK-6.
