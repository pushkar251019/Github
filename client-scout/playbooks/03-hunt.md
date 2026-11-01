# Hunt — find, study, qualify, enrich, draft

Arguments: industry + city (e.g. `dentist in Austin, TX`). If none given, take the next row of the
search plan in `icp.md`. Read `icp.md` first. Default batch: 40 businesses.

## 1. Discover
```
bin/scout find --industry "<industry>" --city "<city>" --radius 10 --limit 40
```
- 0 results? try `bin/scout industries`, a wider `--radius`, an explicit `--tag`, or `--include-no-website`
  (only if the offer is building websites).
- Top up coverage with web search (if you have a search tool): query
  `"<industry>" "<city>"` / `best <industry> in <city>` and add real independent businesses:
  `bin/scout add --name "..." --website "..." --city "..." --industry "..." --source web`.
  Skip directories (Yelp, Healthgrades, etc.) — add the business's own site.

## 2. Study websites (cheap, deterministic)
```
bin/scout analyze --status new --limit 40
```

## 3. Qualify (your judgment, against icp.md)
For each `bin/scout leads --status analyzed --json` lead — use the `lead-qualifier` subagent in parallel
batches of ~5 when available, otherwise do it yourself:
1. `bin/scout show <id> --text` → read signals, health, people, emails and the page text.
2. Ad library: `site.running_ads_likely` comes from tracking pixels. If the score hinges on ads and you have
   a web fetch tool, open `site.ads.meta_ad_library` / `google_ads_transparency`; note what they're running
   (offer, angle, how long). If the page won't load, rely on pixels and say so ("pixel present").
3. Score with the rubric. Write a one-line **reason** and one concrete **hook** — a specific, verifiable
   observation tied to the offer (e.g. "Google Ads tag live but no online booking; 'call to book' only").
```
bin/scout qualify <id> --score 82 --reason "..." --hook "..."
bin/scout disqualify <id> --reason "franchise"     # clear misfits
```

## 4. Find the decision-maker + verified email
For each qualified lead:
1. Owner name: from `site.people` (check it in the page text — must be a real person tied to *this*
   business, with an owner/founder/principal-type role). If absent and you have web search, try
   `"<business name>" owner` / `founder` / LinkedIn, the state business registry, or press mentions.
   Only record names you found in a source; note the source.
   ```
   bin/scout contact <id> --name "Jane Smith" --role "Owner" --source "about page"
   ```
2. `bin/scout findemail <id>` → status meanings:
   - `valid` — SMTP-verified mailbox. Best.
   - `published` — listed on their site (matches the person). Good.
   - `catch_all` — domain accepts everything; pattern guess. OK at low volume.
   - `unknown` — couldn't verify (port 25 blocked). Use only `published` or `first@` on small firms; mention risk.
   - `generic` — info@/hello@. Fine for 1–5 person businesses; open with the owner's name if known.
   - `not_found` / `no_mx` — lead goes to `no_email`; skip.

## 5. Draft the first email
Follow `04-write.md` for each enriched lead, then:
```
bin/scout draft <id> --kind initial --subject "..." --body-file /tmp/email_<id>.txt
```
(In `auto` mode add `--approve` only if it passes the 04 checklist.)

## 6. Report
`bin/scout stats` + a short table: business, score, hook, contact, email status. Tell the user to review
with `/scout-send` (or that sends will go out in the next window in auto mode).
