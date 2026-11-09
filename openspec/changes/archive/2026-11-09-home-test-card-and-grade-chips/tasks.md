# Tasks

## 1. The data and the screen

- [x] 1.1 Make `GET /api/home` list only the nearest test's weak practice tests; verify API tests: a weak practice test of the nearest test is listed, one of a later test is not
- [x] 1.2 Put the weak practice tests inside the nearest test's card (no separate card) and show the grades as chips inside the "בוחן" link and inside each retake button; verify Playwright tests: the weak tests are inside `#nearest-test` under its readiness and task, there is no separate card, a chip holds the bare grade or "-", the chip is inside its link, no sideways scrolling at 360px

## 2. Wrap-up

- [x] 2.1 Update the PRD (STU-1); run the full suite and `openspec validate home-test-card-and-grade-chips --strict`; verify both pass
