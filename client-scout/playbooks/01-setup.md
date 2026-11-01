# Setup — learn the business (run once, update anytime)

Goal: a complete `scout.json` so every later step can sell this business accurately.

1. Run `bin/scout init` if `scout.json` doesn't exist, then `bin/scout doctor`.
2. Interview the user — **one short message, max 8 questions**, skip anything already in `scout.json`
   or that you can read from their website (ask for the URL first and fetch it to pre-fill):
   - What do you sell, to whom, and what result does it produce? (in their words)
   - Price range / typical deal size.
   - 1–3 proof points: real client results, numbers, names they're allowed to mention.
   - Who is your best current customer and why? Who was your worst?
   - Which cities/regions and industries do you want to target first?
   - Booking link (Calendly/Cal.com/Google appointment page).
   - Sender name, sending email, business postal address (legally required in cold email).
   - Tone: how do you talk to clients?
3. Write answers into `scout.json` (`business.*`, `sender.*`) with `bin/scout config --set key=value`
   or by editing the file. Keep `business.description` to 2–3 sentences in plain English.
4. Mailbox: explain the free route — Gmail/Google Workspace with an **App Password**
   (Google Account → Security → 2-Step Verification → App passwords), then `export SCOUT_EMAIL_PASSWORD=...`
   in their shell profile. Set `smtp.user`/`imap.user`. Other providers: set host/port.
   Strongly recommend a **separate sending domain or mailbox** (e.g. `name@get<brand>.com`) with SPF, DKIM
   and DMARC set, warmed up for 2–3 weeks at low volume, so their main domain's reputation is safe.
5. Set `sending.timezone` (IANA, e.g. `Asia/Kolkata`, `America/New_York`) and keep `daily_limit` ≤ 30
   for a new mailbox (raise gradually to 50 max per mailbox).
6. Run `bin/scout doctor --network` and report what's green and what's missing.
7. Then run the ICP playbook (`02-icp.md`).
