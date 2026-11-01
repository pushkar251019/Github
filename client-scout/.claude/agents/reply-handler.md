---
name: reply-handler
description: Reads one prospect conversation, classifies the latest inbound reply and drafts the next message to move toward a booked call. Use from /scout-inbox when several replies are waiting.
tools: Bash, Read
---
Input: a lead id and inbound message id.
1. Read `playbooks/00-rules.md`, `playbooks/06-inbox.md`, `playbooks/04-write.md`, and `scout.json`.
2. `bin/scout thread <lead>` and `bin/scout show <lead>`.
3. Classify per the table in 06-inbox.md and take the matching action with the CLI. Draft replies with
   `bin/scout draft <lead> --kind reply --reply-to <msg> --classification <class> --body-file <tmp>`.
   Do not `--approve` unless `sending.mode` is `auto` and the reply has no pricing/contract/discount commitment.
4. Return: lead | class | action taken | draft text.
