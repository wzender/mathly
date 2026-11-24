## Why

A photographed question showed LaTeX code ("\triangle ABC … 30^\circ … 18\text{ ס"מ}") because the AI wrote LaTeX commands while the app draws math as plain symbols, and an empty "()" where the AI dropped a given. The student could not check what was read, because the photo was hidden in a closed section.

## What Changes

- The AI reading and tutor prompts ask for plain symbols (△ ∠ ⊥ ° √ ²) and no LaTeX commands, and for every given, including what is in brackets.
- LaTeX the AI writes anyway is shown as symbols (new `mathly2/mathtext.py`), at view time too, so questions already kept are fixed; an empty "()" is dropped.
- The photo shows open above the question; a tap enlarges it.

## Impact

`mathly2/mathtext.py`, `mathly2/photoq.py`, `mathly2/boardreview.py`, `mathly2/static/photoq.js`, `mathly2/static/app.css`. No migration.
