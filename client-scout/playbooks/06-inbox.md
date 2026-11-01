# Inbox — keep every conversation moving until the call is booked

1. `bin/scout inbox` (IMAP sync). It auto-handles bounces (suppress + mark bounced), auto-replies, and clear
   unsubscribes, cancels pending follow-ups for anyone who replied, and lists conversations needing a response.
   (No IMAP? If a Gmail connector is available, search `in:inbox newer_than:14d` for replies from leads'
   addresses, save each as .eml if possible and use `bin/scout inbox --file`, or summarise and continue.)
2. For each inbound message: `bin/scout thread <lead id>` and `bin/scout show <lead id>` for context.
3. Classify (store it via the reply or `handled`):
   | class | meaning | action |
   |---|---|---|
   | `interested` | wants to talk / asks for time | reply with booking link + 2 specific time options; status `interested` |
   | `question` | asks price, how it works, who you are | answer in ≤ 80 words, honestly, from scout.json; end by offering the call |
   | `objection` | "too expensive", "we have someone", "bad timing" | acknowledge, one reframe or proof, low-pressure call offer; never argue twice |
   | `referral` | "talk to X instead" | thank them; draft to the new person referencing the referral (add contact first) |
   | `not_now` | "reach out in Q2" | thank; `bin/scout set <id> --status lost notes="revisit <date>"`; tell user to set a reminder |
   | `booked` | confirms a time / booked via link | thank + confirm; `bin/scout set <id> --status booked`; notify the user prominently |
   | `unsubscribe` / `not_interested` | any no | short courteous close only if they asked a question, otherwise no reply; `bin/scout set <id> --status unsubscribed` |
   | `auto_reply` | OOO | `bin/scout handled <msg> --classification auto_reply`; keep sequence |
4. Write the reply (see `04-write.md` tone rules; warm replies ≤ 90 words; mirror their length and formality;
   answer their actual question first). Save it in-thread:
   ```
   bin/scout draft <lead id> --kind reply --reply-to <inbound msg id> --classification interested --body-file /tmp/r.txt
   ```
   Add `--approve` only in auto mode and only if it contains no pricing commitment, discount, contract, or
   promise the user hasn't pre-approved in scout.json. Then `bin/scout send` (replies skip the window, never the cap).
5. Status: `bin/scout set <id> --status interested` once they show intent.
6. Report: who replied, how you classified each, what you sent / queued, and **any booked calls first**.
