# Tasks

## 1. The board

- [x] 1.1 Make the held right mouse button (and the pen's barrel button) erase and show the eraser's cursor while held, without opening the context menu and without changing the chosen tool; verify Playwright tests: with the pen chosen, a right-button drag erases a stroke, the pen is still chosen and still draws with the left button, no context menu, the eraser size is the chosen one
- [x] 1.2 Place the question's copy at the top of a question's sketch by itself the first time it is shown (exercise screen, quiz, practice test, simulation), once per sketch; verify Playwright tests: the question's text is on the board when it opens, the next question has its own, a deleted copy does not return after leaving and coming back, the "השאלה" button still adds one, the eraser leaves it alone

## 2. Wrap-up

- [x] 2.1 Update the PRD (BRD-3, BRD-6); run the full suite and `openspec validate board-question-and-right-click-eraser --strict`; verify both pass
