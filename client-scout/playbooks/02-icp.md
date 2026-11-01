# Build the Ideal Customer Profile → `icp.md`

Input: `scout.json` business profile (+ the user's website if given, + any customer list they share).
Output: `icp.md` at repo root, in exactly this structure. Be specific; vague ICPs produce spam.

```markdown
# ICP — <business name>   (updated <date>)

## Offer in one line
<who it's for> get <outcome> via <mechanism>, without <pain>.

## Who buys
- Industries (ranked, with why): ...
- Size: employees / locations / revenue proxy (e.g. "1–3 locations, 5–40 staff")
- Geography: ...
- Decision-maker titles (in order): Owner, Founder, Practice Manager, ...

## Pains we solve (in their words)
- ...

## Buying signals we can SEE on a website / ad library   (each with points)
- +20 runs paid ads (Meta pixel / Google Ads tag / active ads in library) → has budget, wants leads
- +15 no online booking / weak CTA / no form → leaking leads we can fix
- ... (tailor to the offer; 6–10 signals, every one detectable by `bin/scout show`)

## Disqualifiers (auto-reject)
- National chains / franchises / enterprise
- Already using <competitor or the exact thing we sell, done well>
- Website down, parked, or no way to reach a decision-maker
- ...

## Scoring rubric (0–100, qualify at >= 70)
- Industry fit: 0–25
- Size fit: 0–15
- Visible pain/opportunity our offer fixes: 0–30
- Budget/intent signals (ads, hiring, growth, new location): 0–20
- Reachability (named owner + email): 0–10

## Angles that work (personalisation hooks to look for)
- e.g. "running Google Ads but sending clicks to a homepage with no booking button"
- ...

## Search plan
| Industry (scout find --industry) | Cities | Radius km | Notes |
|---|---|---|---|
```

Steps:
1. Draft it from what you know; derive signals from what our analyzer actually detects:
   `signals` (meta_pixel, google_ads, google_analytics, google_tag_manager, tiktok_pixel, linkedin_insight,
   microsoft_ads, wordpress, wix, squarespace, shopify, webflow, godaddy_builder, online_booking, live_chat,
   reviews_widget, email_capture, ecommerce), `health` (https, mobile_viewport, stale_copyright, load_seconds,
   has_blog, has_testimonials, has_pricing, has_cta_form), `socials`, `people`, plus the page text.
2. For the search plan, map each industry to `bin/scout industries` names (or an OSM `--tag key=value`).
3. Show the user a 6-line summary and ask for corrections. Save to `icp.md`.
