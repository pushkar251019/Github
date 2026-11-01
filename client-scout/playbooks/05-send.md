# Send — review and send the queue

1. `bin/scout queue` — show every draft. For each, present to the user compactly:
   `#msg | business | to | subject | first line`, then the full bodies if they want.
2. Apply edits the user asks for: `bin/scout edit <msg> --subject ... --body-file ...` or `--discard`.
3. Approve: `bin/scout approve <msg ids...>` or `bin/scout approve --all` (only with explicit user OK in review mode).
4. Preview one: `bin/scout send --dry-run --max 1` (shows the exact email incl. footer).
5. Send: `bin/scout send` — respects window, daily cap and spacing (it sleeps between sends; for 30 emails
   expect ~60 minutes — run it in the background if your harness supports that).
6. Report the CLI's actual output: sent N, skipped (why), remaining. If it stopped for "outside window" or
   "daily limit", say when the next window opens.
