# Proposal

## Why

Under the readiness number the parts are written as "M שליטה 0", "E מבחני תרגול 13", "S סימולציה —": the letters mean nothing to a student and nothing says what each number is.

## What Changes

- **Each part is a row in plain Hebrew**: its name, a short line saying what the number is, and the value: "שליטה: אחוז המיומנויות שנשלטו — 0%", "מבחני תרגול: ממוצע הציונים הטובים ביותר — 13", "סימולציה: הציון במבחן הסימולציה — —". The letters M, E and S are not shown.
- A part with no value yet shows "—".

## Capabilities

### Modified Capabilities
- `readiness-meter`: "One readiness number".

## Impact

- `home.js`, `app.css`, the browser tests that read the parts; PRD RDY-1. No server or database change.
