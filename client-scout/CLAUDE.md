# Client Scout

This repo turns the agent into the user's sales rep. Its only job is to book qualified calls.

- Always start by reading `playbooks/00-rules.md`.
- Slash commands in `.claude/commands/` map 1:1 to `playbooks/`: `/scout-setup`, `/scout-icp`, `/scout-hunt <industry> in <city>`,
  `/scout-send`, `/scout-inbox`, `/scout-followup`, `/scout-daily`, `/scout-status`, `/scout-write <id>`.
- Run the CLI as `bin/scout ...` (Python 3.9+, standard library only). Tests: `python3 -m unittest discover -s tests`.
- `scout.json`, `icp.md` and `.scout/` hold the user's private data and are git-ignored. Never commit them.
- If the user just says "find me clients" with no setup done, run `/scout-setup` first.
