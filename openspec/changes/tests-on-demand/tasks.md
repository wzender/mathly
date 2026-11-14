## 1. Server
- [x] 1.1 `readiness.py`: tests-only number with GAIN per kind, levels, next level, what a perfect test adds, a test's change
- [x] 1.2 `realtests.py`: facts from all practice tests and simulations; the card's practice modes, simulations and trail; remove the plan and today's task
- [x] 1.3 `POST /api/tests/{id}/practice/start` (balanced, focus, manual); simulations on request; old `/exercise/{n}/start` kept
- [x] 1.4 A result carries its readiness change; grades grouped by mode; teacher tabs show counts and bests
- [x] 1.5 Remove `countdown.py`

## 2. Screens
- [x] 2.1 Home: one compact block with the number, the level, the days left and two buttons with "+N"; still one screen
- [x] 2.2 Test page: the readiness meter and how it goes up, simulation on request, practice test with the three modes, the trail of gains
- [x] 2.3 Result: the gain, the bar growing, a new level, buttons for the next test
- [x] 2.4 Teacher tests tab and progress tab

## 3. Tests
- [x] 3.1 Readiness unit tests; API tests for modes, simulations on demand, readiness change, grades
- [x] 3.2 Browser tests: home block, simulation with a level up, test page modes and trail; home fits one screen
