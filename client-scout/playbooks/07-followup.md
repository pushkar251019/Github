# Follow-ups — no lead forgotten

1. `bin/scout due --json` — leads where the next sequence step is due (default days 3, 7, 14 after the first
   email; skips anyone who replied, bounced or unsubscribed; marks finished sequences as `lost` after a week).
2. Before writing, run `bin/scout inbox` so you don't follow up someone who just replied.
3. For each due lead: `bin/scout thread <id>` + `bin/scout show <id> --text`; write follow-up #N per `04-write.md`
   with a **new** angle; save with `bin/scout draft <id> --kind followup --body-file ...` (subject is threaded automatically).
4. Review/auto-approve per mode, then `bin/scout send`.
