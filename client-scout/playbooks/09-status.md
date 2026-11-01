# Status — pipeline dashboard

1. `bin/scout stats` and `bin/scout leads --status interested,replied,booked`.
2. Present: funnel (found → qualified → contacted → replied → booked), reply rate, booked calls (names),
   conversations waiting on the user, drafts awaiting approval, follow-ups due (`bin/scout due`).
3. One diagnosis + one recommendation, based on the numbers:
   - reply rate < 3% after 100 sends → angle/ICP problem: tighten hooks or switch segment
   - bounces > 3% → email finding too loose: only `valid`/`published` for a while
   - many replies, few bookings → reply handling: shorten, lead with the booking link + times
