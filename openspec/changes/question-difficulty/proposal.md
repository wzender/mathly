## Why

Practice should build up from easy to hard; the practice tests should not spend questions on easy ones, and the simulation should be harder than the practice tests.

## What Changes

- Every one of the bank's 1050 questions gets a difficulty (1 easy, 2 medium, 3 hard) by hand-checked criteria, in `content/difficulty.json` (`mathly2/difficulty.py`).
- A skill's practice round and a lesson round go from easy to hard.
- Practice tests take medium and hard questions only, 40% hard; the simulation 60% hard (1.5 times). Easy ones only when nothing else can fill the test.

## Impact

New `mathly2/difficulty.py`, `mathly2/content/difficulty.json`; `mathly2/learning.py`, `mathly2/rounds.py`, `mathly2/exam.py`, `mathly2/realtests.py`. No migration.
