# Tasks

## 1. The indicator

- [x] 1.1 Show the thinking indicator on a tapped choice in `exercise.js` with its styles (spinner, dimmed other choices, status line, still under reduced motion); verify a Playwright test that delays the answer by 1.5 seconds: during the wait the tapped choice has the spinner, "בודקים…" shows, the other choices are disabled, then the result replaces them; and that after an error the choices work again
- [x] 1.2 Add the PRD line; verify `openspec validate show-answer-pending --strict` and the exercise tests pass
