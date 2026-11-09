# Tasks

## 1. The list as cards

- [x] 1.1 Make `GET /api/review` return the waiting questions grouped by skill (the skills in the bank's order, each skill's questions oldest first, no right choice) and `POST /api/review/answer` return the result and the new counts without choosing a next question; verify API tests for the groups, the order, the counts after a right and a wrong answer, and that nothing reveals the right choice
- [x] 1.2 Make the חזרה screen show the cards grouped by skill, answered in place, with "נסו שוב" after a wrong answer; verify Playwright tests: two skills show two headings with their cards, a right answer marks the card done and lowers both counts, the last card of a skill removes its heading, a wrong answer keeps the card with the mistake and no right choice and "נסו שוב" works, the empty state, no sideways scrolling at 320px
- [x] 1.3 Update the PRD (STU-8); run the full suite and `openspec validate review-cards-by-skill --strict`; verify both pass
