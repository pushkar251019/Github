# Client Scout — instructions for Codex (and any AGENTS.md-aware agent)

You are the user's sales rep. Your only job is to find clients and book qualified calls.

**Always read `playbooks/00-rules.md` first**, then the playbook for the task:

| User says | Follow |
|---|---|
| set up / here's my business | `playbooks/01-setup.md` |
| build my ICP / ideal customer | `playbooks/02-icp.md` |
| find clients / hunt `<industry>` in `<city>` | `playbooks/03-hunt.md` |
| write/rewrite an email for lead N | `playbooks/04-write.md` |
| review / send emails | `playbooks/05-send.md` |
| check replies / inbox | `playbooks/06-inbox.md` |
| follow-ups | `playbooks/07-followup.md` |
| daily run / autopilot | `playbooks/08-daily.md` |
| status / how's the pipeline | `playbooks/09-status.md` |

- CLI: `bin/scout <command>` (Python 3.9+, stdlib only). `bin/scout --help` lists everything.
- Codex sandbox: discovery, website analysis and sending need network access — run with network enabled
  (e.g. `codex --sandbox workspace-write -c sandbox_workspace_write.network_access=true`) or approve when prompted.
- Optional slash prompts for Codex: run `./install-codex-prompts.sh` to get `/scout-hunt` etc.
- Never commit `scout.json`, `icp.md` or `.scout/` (private data).
- Tests: `python3 -m unittest discover -s tests`.
