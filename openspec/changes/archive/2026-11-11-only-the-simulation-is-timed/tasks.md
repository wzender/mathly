# Tasks

## 1. Timing

- [x] 1.1 Hold only simulation attempts to their deadline (`TIMED_KINDS`); give an untimed attempt a null `due_at` in its view; verify tests: a quiz and an exercise test stay open long after their stored `due_at` and a late submit is not a timeout, the simulation still times out
- [x] 1.2 Show no timer on the sheet when the attempt has no `due_at`; verify Playwright tests: a quiz and an exercise test show no timer, a quiz past its old deadline is still open with its answers, the simulation shows its minutes and is handed in when its countdown reaches zero

## 2. Wrap-up

- [x] 2.1 Update the PRD (QZ-2, QZ-5, EXT-4, EXT-7, GRD-2) and run the full suite
