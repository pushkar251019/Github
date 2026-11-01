# Client Scout 🎯 — a free, open-source AI sales rep for Claude Code & Codex

**Its only job: find you clients and book calls.**

Install it, tell it what your business does, and it will:

1. **Build your Ideal Customer Profile** (`icp.md`) with a scoring rubric and search plan.
2. **Search business listings** in the cities and industries you choose (OpenStreetMap, plus web search when your agent has it).
3. **Study each website and ad footprint**: Meta/Google/TikTok ad pixels, Ad Library links, booking widgets, site builder, site health, owner names, contact details.
4. **Pick only the ones that fit your offer**, scoring each 0–100 against your ICP with a written reason and a personalisation hook.
5. **Find the owner's name and an email**, verified over SMTP (with catch-all detection) when your network allows it.
6. **Write each one a hyper-personalised email** based on what it actually saw, and sends it from your own mailbox.
7. **Reads replies and keeps the conversation going**: answers questions, handles objections and sends your booking link until the call is booked.
8. **Follows up automatically** on days 3, 7 and 14, in the same thread, with a new angle each time, and stops the moment someone replies.

No subscriptions and no API keys. Python standard library only, with a local SQLite CRM.

---

## Install (2 minutes)

```bash
git clone <this repo> && cd client-scout     # or copy the client-scout/ folder anywhere
bin/scout init                               # creates scout.json + local database
claude                                       # or: codex
```
Then type:
```
/scout-setup https://your-website.com
```
It interviews you (≤ 8 questions), fills in `scout.json`, then builds your ICP. After that:

| Command | What it does |
|---|---|
| `/scout-hunt dentist in Austin, TX` | find → analyse → qualify → find owner + email → draft emails |
| `/scout-send` | review, approve, send (respecting limits) |
| `/scout-inbox` | read replies, classify, respond, push to a booked call |
| `/scout-followup` | draft + send due follow-ups |
| `/scout-daily` | all of the above, then a 10-line report |
| `/scout-status` | funnel, reply rate, booked calls, and a diagnosis |
| `/scout-write 42` | write or rewrite the email for lead #42 |

**Codex:** `AGENTS.md` routes plain requests ("find me dentists in Austin") to the same playbooks. For slash prompts run `./install-codex-prompts.sh`. Give Codex network access for discovery and sending.

**Run it on autopilot:**
```bash
# inside Claude Code
/loop 24h /scout-daily
# or cron, weekdays 9:15
15 9 * * 1-5 cd ~/client-scout && claude -p "/scout-daily" --permission-mode acceptEdits
15 9 * * 1-5 cd ~/client-scout && codex exec "Follow playbooks/08-daily.md"
```

## Connect your mailbox (free)
Gmail / Google Workspace: turn on 2-Step Verification, create an **App Password**, then:
```bash
export SCOUT_EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"   # add to ~/.zshrc or ~/.bashrc
bin/scout config --set smtp.user=you@yourdomain.com imap.user=you@yourdomain.com sender.email=you@yourdomain.com
bin/scout doctor --network
```
For other providers, set `smtp.host/port` and `imap.host/port` in `scout.json`. If you have the Gmail connector in Claude, the agent can use it instead.

## How it works
```
 Claude Code / Codex  (the brain: ICP, judgement, writing, conversations)
        │  follows playbooks/*.md
        ▼
 bin/scout  (the hands: deterministic, rate-limited, logged)
   find ── OpenStreetMap Overpass + Nominatim (free, legal open data)
   analyze ─ website crawl (robots.txt respected): emails, people, pixels, tech, health
   findemail ─ published-email match → name patterns → DNS MX + SMTP RCPT probe + catch-all test
   draft/approve/send ─ your SMTP, daily cap, window, spacing+jitter, suppression, opt-out footer
   inbox ─ IMAP sync, thread matching, bounce/OOO/unsubscribe detection, follow-up cancellation
   due ─ sequence engine (3/7/14 days, then marks the lead lost)
        ▼
 .scout/scout.db  (your private CRM; `bin/scout export` for CSV)
```

## Safety rails (enforced in code, not just prompts)
- **Review mode by default.** Nothing sends until you approve. Switch with `bin/scout config --set sending.mode=auto`.
- Daily cap (30 by default), sending window, weekdays only, 90 s ± jitter between emails.
- Suppression list checked before every send. Unsubscribes and bounces are added automatically.
- Every cold email gets your identity, your postal address, an opt-out line and a `List-Unsubscribe` header.
- Follow-ups are cancelled the moment a human replies.
- Pricing, discounts and contracts are never auto-sent. They always wait for you.

## Honest limits (read this)
- **"Free" covers the software.** You still need a mailbox, and ideally a separate sending domain (about $10/yr) with SPF, DKIM and DMARC, warmed up for 2–3 weeks. Cold email sent from your main domain at volume can damage its reputation.
- **Coverage:** OpenStreetMap is strong in some places and patchy in others. The agent tops it up with web search. You can also `bin/scout import any.csv`. It does **not** scrape Google Maps or LinkedIn, because that breaks their terms.
- **Email verification** needs outbound port 25. Many home ISPs and cloud hosts block it. The tool then marks emails `unknown` or `published` and won't call them verified. Run `bin/scout doctor --network` to check.
- **Ad libraries:** pixel detection always works. Meta's Ad Library and Google's Ads Transparency pages are JavaScript-heavy. The agent opens them when its browser/fetch tool can render them; otherwise it relies on the pixel signal and says so.
- **AI judgement can be wrong.** In review mode, read what you send.

## Compliance
You are the sender and you are responsible. Short version, not legal advice:
- **US (CAN-SPAM):** B2B cold email is allowed with honest headers and subject, your physical address and a working opt-out honoured within 10 days. The tool honours opt-outs instantly.
- **EU/UK (GDPR, PECR):** B2B outreach to corporate addresses can rely on legitimate interest if it's relevant to the person's role. UK sole traders and partnerships count as individuals and need consent. Keep a record of why each lead is relevant (the tool stores `fit_reason`).
- **Canada (CASL):** stricter. Implied consent applies only when an address is conspicuously published, carries no "no solicitation" notice, and your message is relevant to the person's role. Skip if unsure.
- **India and elsewhere:** follow local rules, and always honour opt-outs.

## CLI reference
`bin/scout --help`. Main commands: `init doctor config industries find add import analyze leads show qualify disqualify set contact findemail verify draft queue approve edit send inbox handled thread due suppress stats export`.

Tests: `python3 -m unittest discover -s tests`. They use a fake local SMTP server and sample replies and bounces.

MIT licensed. PRs welcome: more industry mappings, listing sources and playbook improvements.
