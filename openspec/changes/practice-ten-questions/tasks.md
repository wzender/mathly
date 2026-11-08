# Tasks

## 1. Ten practice questions

- [x] 1.1 Add `Bank.practice_keys(skill_id)` (the first 10 question keys of the skill) and use it for the exercise screen's count, dots, progress and next question; verify tests: a skill with 30 questions gives total 10 and only questions from its first 10, a skill with 10 or fewer is unchanged, a student whose current question is outside the first 10 is moved to a practice question, answering grades any question of the skill, and quizzes, exercise tests and the simulation still draw from all 30
- [x] 1.2 Add the PRD lines; verify `openspec validate practice-ten-questions --strict`, the mathly2 tests pass, and the exercise screen of `t_ext` shows "מתוך 10" in a browser
