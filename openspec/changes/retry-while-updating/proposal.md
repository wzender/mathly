## Why

During each update the host restarts the site; requests then got the host's 503 and the sign-in always said "שירות ההתחברות לא זמין", though nothing was wrong with signing in.

## What Changes

- A 502/503/504 without the server's JSON, or a failed connection, is sent again over about half a minute with a "האתר מתעדכן" note; then a clear message.
- A 503 from the server itself is not sent again; the sign-in shows the real reason. The server's sign-in 503 is in Hebrew.

## Impact

`mathly2/static/api.js`, `mathly2/static/app.js`, `mathly2/static/app.css`, `mathly2/auth.py`. No migration.
