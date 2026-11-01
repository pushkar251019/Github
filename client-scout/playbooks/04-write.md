# Writing — hyper-personalised cold email that gets replies

Read: `scout.json` (offer, proof, tone, booking link, sender), `icp.md`, and `bin/scout show <id> --text`.

## The shape (first email) — 50–110 words, plain text, no images, no links except optionally the site
1. **Subject**: 2–5 words, lowercase-ish, specific to them. e.g. `booking on smilecraft`, `question about your ads`.
   No clickbait, no "Re:" on a first email, no emoji, no ALL CAPS.
2. **Line 1 – the observation** (their world, not yours): one specific, true thing you saw that relates to the
   pain. Name the page/ad/detail. ("Saw you're running Google Ads for implants, but the landing page only
   offers a phone number after 5pm.")
3. **Line 2 – why it matters** in their money/time terms (one sentence, no lecture).
4. **Line 3 – proof**: one real result from `business.proof`, ideally same industry. Never invent numbers.
5. **Line 4 – soft CTA, interest-based**: "Worth a 15-min look?" / "Want me to send the 3 fixes?"
   — not the booking link in email 1 (links hurt deliverability and feel salesy). Offer value first.
6. Sign-off: first name only (signature + opt-out + address are appended by the CLI — don't add them).

Greeting: `Hi <first name>,` if known, else `Hi <Business> team,`.

## Follow-ups (`--kind followup`, sent in the same thread; subject auto = "Re: ...")
- #1 (day 3): 30–60 words. New angle or a small free win (one actionable tip specific to their site).
- #2 (day 7): 30–50 words. Social proof / short case example, or a question about priorities.
- #3 (day 14, breakup): 2–3 lines. "Should I close the loop on this?" — polite, no guilt.
Never repeat the first email. Never "just bumping this". Each must stand alone.

## Replies (warm conversation) — see `06-inbox.md`
Here the **booking link IS used**: `sender.booking_link`.

## Checklist before saving (all must be true)
- [ ] Every claim about them is verifiable in `show --text` output or a page you fetched
- [ ] Mentions something only true of *this* business (would be wrong if sent to a competitor)
- [ ] One CTA, one question mark max in the CTA
- [ ] ≤ 110 words (first) / ≤ 60 (follow-ups); no buzzwords ("synergy", "revolutionize", "game-changer", "I hope this finds you well")
- [ ] No fake personal familiarity, no "quick question" + 3 questions, no fake Re:/Fwd:
- [ ] Reads like a human wrote it to one person on their phone

## Example (structure only — names and numbers are placeholders; use only real proof from scout.json)
Subject: `new patient form`
> Hi Dr. Patel,
>
> Noticed Riverside Dental is running Meta ads for Invisalign, but the "Book" button on your site goes to a
> contact form with no reply-time promise.
>
> Most of those clicks come in evenings, when no one's there to call back.
>
> We set up instant online booking for Lakeview Ortho and their ad leads booked 31% more consults in 6 weeks.
>
> Worth me sending over a 2-minute walkthrough of how it'd look on your site?
>
> Sam
