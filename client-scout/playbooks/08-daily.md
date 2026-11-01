# Daily autopilot — one command, the whole job

Run in this order, stopping early only for errors or when the user's input is required:

1. `bin/scout doctor` — abort with a clear message if config is broken.
2. **Inbox first** (`06-inbox.md`) — warm conversations beat cold ones.
3. **Follow-ups** (`07-followup.md`).
4. **Top up the pipeline**: if fewer than `daily_limit` initial drafts are waiting
   (`bin/scout stats`), run `03-hunt.md` on the next search-plan row in `icp.md` until there are enough.
   Track which rows are done by appending `✅ <date>` to that row.
5. **Send** (`05-send.md`): in `review` mode, stop and present the queue for approval; in `auto` mode send.
6. **Report** in ≤ 10 lines: booked calls, new replies, sent today/limit, new qualified leads, anything
   that needs the user. Nothing else.

## Scheduling (tell the user how, don't assume)
- Inside a session: `/loop 24h /scout-daily` (or self-paced `/loop /scout-daily`).
- Headless (cron, weekdays 9:15):
  `15 9 * * 1-5 cd /path/to/client-scout && claude -p "/scout-daily" --permission-mode acceptEdits`
- Codex: `15 9 * * 1-5 cd /path/to/client-scout && codex exec "Follow playbooks/08-daily.md"`
  Inbox-only checks can run more often, e.g. hourly 9–18: `claude -p "/scout-inbox"`.
