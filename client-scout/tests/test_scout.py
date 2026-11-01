import json
import os
import socketserver
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scout import cli, config, emailfind, listings, mailer, site  # noqa: E402
from scout.db import DB  # noqa: E402

HTML = """<html><head><title>Riverside Dental | Austin Dentist</title>
<meta name="viewport" content="width=device-width"><meta name="description" content="Family dentist in Austin">
<script src="https://connect.facebook.net/en_US/fbevents.js"></script><script>fbq('init','123');</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-123456789"></script>
<link href="/wp-content/themes/x.css">
<script type="application/ld+json">{"@type":"Dentist","name":"Riverside Dental","founder":{"@type":"Person","name":"Priya Patel","jobTitle":"Owner & Lead Dentist"}}</script>
</head><body><h1>Welcome</h1><p>Meet Dr. Priya Patel, DDS - founder of Riverside Dental.</p>
<a href="/about-us">About Us</a> <a href="/team">Our Team</a> <a href="https://othersite.com/x">x</a>
<a href="mailto:hello@riversidedental.com">Email</a> <p>Call (512) 555-0134</p>
<p>office [at] riversidedental [dot] com</p>
<a href="https://www.instagram.com/riversidedental">IG</a>
<p>&copy; 2019 Riverside Dental</p><img src="logo@2x.png"></body></html>"""


class FakeSMTP(socketserver.StreamRequestHandler):
    received = []

    def handle(self):
        w = lambda s: self.wfile.write((s + "\r\n").encode())
        w("220 fake ESMTP")
        data_mode, buf, rcpts = False, [], []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            s = line.decode().rstrip("\r\n")
            if data_mode:
                if s == ".":
                    data_mode = False
                    FakeSMTP.received.append({"rcpt": rcpts[:], "data": "\n".join(buf)})
                    buf = []
                    w("250 queued")
                else:
                    buf.append(s[1:] if s.startswith("..") else s)
                continue
            cmd = s[:4].upper()
            if cmd in ("EHLO",):
                w("250-fake\r\n250 AUTH PLAIN LOGIN")
            elif cmd == "HELO":
                w("250 fake")
            elif cmd == "AUTH":
                w("235 ok")
            elif cmd == "MAIL":
                rcpts = []
                w("250 ok")
            elif cmd == "RCPT":
                addr = s.split(":", 1)[1].strip("<> ")
                if addr.startswith("nobody") or addr.startswith("zz"):
                    w("550 no such user")
                else:
                    rcpts.append(addr)
                    w("250 ok")
            elif cmd == "DATA":
                data_mode = True
                w("354 go")
            elif cmd == "QUIT":
                w("221 bye")
                return
            else:
                w("250 ok")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        cfgdata = json.loads((ROOT / "scout.example.json").read_text())
        cfgdata["sender"].update({"name": "Sam Lee", "email": "sam@growthco.test", "signature": "Sam Lee\nGrowthCo",
                                  "physical_address": "1 Main St, Austin TX", "booking_link": "https://cal.test/sam"})
        cfgdata["smtp"].update({"host": "127.0.0.1", "user": "sam@growthco.test"})
        cfgdata["sending"].update({"window_hours": [0, 24], "weekdays_only": False, "daily_limit": 2})
        (self.home / "scout.json").write_text(json.dumps(cfgdata))
        os.environ["SCOUT_HOME"] = str(self.home)
        os.environ["SCOUT_EMAIL_PASSWORD"] = "x"
        self.cfg = config.load()
        self.db = DB(config.data_dir(self.cfg) / "scout.db")

    def tearDown(self):
        os.environ.pop("SCOUT_HOME", None)
        self.tmp.cleanup()


class TestSite(unittest.TestCase):
    def test_extraction(self):
        p = site.parse_html(HTML)
        text = site.clean_text(p.text)
        emails = site.extract_emails(HTML, text, "riversidedental.com")
        self.assertIn("hello@riversidedental.com", emails)
        self.assertIn("office@riversidedental.com", emails)
        self.assertFalse(any("2x" in e for e in emails))
        sig = site.detect_signals(HTML)
        for s in ("meta_pixel", "google_ads", "wordpress"):
            self.assertIn(s, sig)
        people = site.extract_people(text, p.jsonld)
        self.assertEqual(people[0]["name"], "Priya Patel")
        self.assertIn("instagram", site.extract_socials(HTML))
        h = site.site_health(HTML, text, p.meta, "https://riversidedental.com", 0.4)
        self.assertTrue(h["stale_copyright"] and h["mobile_viewport"])
        pages = site.candidate_pages("https://riversidedental.com/", p.links)
        self.assertEqual(len(pages), 2)
        self.assertTrue(all("othersite" not in u for u in pages))

    def test_analyze_with_fake_fetch(self):
        class R:
            def __init__(s, url, text):
                s.url = s.final_url = url; s.text = text; s.status = 200; s.elapsed = 0.3; s.ok = True
        with mock.patch("scout.net.fetch", side_effect=lambda url, *a, **k: R(url, HTML)):
            data, text = site.analyze("riversidedental.com", "ua", "Riverside Dental")
        self.assertTrue(data["running_ads_likely"])
        self.assertEqual(data["domain"], "riversidedental.com")
        self.assertIn("[PAGE]", text)


class TestListings(unittest.TestCase):
    def test_tags_and_query(self):
        tags = listings.resolve_tags("dentists", ["shop=foo"])
        self.assertIn("amenity=dentist", tags)
        q = listings.build_query(tags, 30.2, -97.7, 5000, require_website=True)
        self.assertIn('nwr["amenity"="dentist"]', q)
        self.assertIn("around:5000,30.2,-97.7", q)

    def test_element(self):
        el = {"type": "node", "id": 7, "lat": 1, "lon": 2,
              "tags": {"name": "Riverside Dental", "website": "riversidedental.com", "addr:city": "Austin"}}
        lead = listings.element_to_lead(el, "dentist", "Austin")
        self.assertEqual(lead["domain"], "riversidedental.com")
        self.assertEqual(lead["source_ref"], "osm:node/7")

    def test_csv(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("Company,URL,Phone\nAcme Plumbing,www.acmeplumb.com,555\n,,\n")
        rows = listings.read_csv(f.name, "plumber", "Denver")
        self.assertEqual(rows[0]["domain"], "acmeplumb.com")
        self.assertEqual(len(rows), 1)


class TestEmailFind(unittest.TestCase):
    def test_patterns_and_names(self):
        self.assertEqual(emailfind.split_name("Dr. Priya K. Patel, DDS"), ("Priya", "Patel"))
        p = emailfind.patterns("José", "O'Neil", "x.com")
        self.assertIn("jose.oneil@x.com", p)
        self.assertEqual(p[0], "jose@x.com")

    def test_find_best_with_smtp(self):
        v = emailfind.Verifier()
        v.mx = lambda d: ["mx.x.com"]
        v._rcpt = lambda mx, addrs: {a: (250 if a == "ppatel@x.com" else 550) for a in addrs}
        r = emailfind.find_best("Priya", "Patel", "x.com", ["hello@x.com"], v)
        self.assertEqual((r["email"], r["status"]), ("ppatel@x.com", "valid"))

    def test_catch_all_never_claims_valid(self):
        v = emailfind.Verifier()
        v.mx = lambda d: ["mx.x.com"]
        v._rcpt = lambda mx, addrs: {a: 250 for a in addrs}
        r = emailfind.find_best("Priya", "Patel", "x.com", [], v)
        self.assertEqual(r["status"], "catch_all")

    def test_port25_blocked_uses_published(self):
        v = emailfind.Verifier()
        v.mx = lambda d: ["mx.x.com"]
        def boom(*a):
            raise OSError("blocked")
        v._rcpt = boom
        r = emailfind.find_best("Priya", "Patel", "x.com", ["priya@x.com", "info@x.com"], v)
        self.assertEqual((r["email"], r["status"]), ("priya@x.com", "published"))
        self.assertTrue(v.port25_blocked)


class TestPipeline(Base):
    def _server(self):
        FakeSMTP.received = []
        srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeSMTP)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.cfg["smtp"]["port"] = srv.server_address[1]
        config.save(self.cfg)
        return srv

    def test_end_to_end(self):
        self._server()
        lid, new = self.db.upsert_lead({"name": "Riverside Dental", "website": "https://riversidedental.com",
                                        "domain": "riversidedental.com", "city": "Austin", "source": "osm",
                                        "source_ref": "osm:node/1"})
        self.assertTrue(new)
        self.assertFalse(self.db.upsert_lead({"name": "dup", "domain": "riversidedental.com"})[1])
        self.db.save_site(lid, {"emails": ["priya@riversidedental.com"], "domain": "riversidedental.com"}, "text")
        cli.main(["qualify", str(lid), "--score", "85", "--reason", "ads, no booking", "--hook", "AW tag live"])
        cli.main(["contact", str(lid), "--name", "Dr. Priya Patel", "--role", "Owner"])
        cli.main(["findemail", str(lid), "--no-probe"])
        c = self.db.primary_contact(lid)
        self.assertEqual((c["email"], c["email_status"]), ("priya@riversidedental.com", "published"))
        cli.main(["draft", str(lid), "--subject", "booking on riverside", "--body", "Hi Priya,\n\nNoticed...\n\nSam"])
        self.assertEqual(self.db.lead(lid)["status"], "queued")
        cli.main(["send", "--no-sleep"])  # nothing approved -> nothing sent
        self.assertEqual(FakeSMTP.received, [])
        cli.main(["approve", "--all"])
        cli.main(["send", "--no-sleep"])
        self.assertEqual(len(FakeSMTP.received), 1)
        data = FakeSMTP.received[0]["data"]
        self.assertIn("List-Unsubscribe", data)
        self.assertIn("1 Main St, Austin TX", data)
        self.assertIn("no thanks", data)
        self.assertEqual(self.db.lead(lid)["status"], "contacted")
        out = self.db.one("SELECT * FROM messages WHERE direction='out' AND status='sent'")

        # follow-up becomes due after 3 days
        old = (datetime.now(timezone.utc) - timedelta(days=4)).replace(microsecond=0).isoformat()
        self.db.update_message(out["id"], sent_at=old)
        with mock.patch("sys.stdout") as so:
            cli.main(["due", "--json"])
        due = json.loads("".join(c.args[0] for c in so.write.call_args_list))
        self.assertEqual(due[0]["followup_number"], 1)
        cli.main(["draft", str(lid), "--kind", "followup", "--body", "One quick idea...", "--approve"])
        fu = self.db.one("SELECT * FROM messages WHERE kind='followup'")
        self.assertEqual(fu["subject"], "Re: booking on riverside")
        self.assertEqual(fu["in_reply_to"], out["message_id"])

        # prospect replies before follow-up is sent -> follow-up cancelled
        reply = (f"From: Priya Patel <priya@riversidedental.com>\r\nTo: sam@growthco.test\r\n"
                 f"Subject: Re: booking on riverside\r\nMessage-ID: <r1@rd.com>\r\nIn-Reply-To: {out['message_id']}\r\n"
                 f"Date: Mon, 2 Nov 2026 10:00:00 +0000\r\n\r\nSounds interesting, what does it cost?\r\n\r\n"
                 f"On Mon, Sam wrote:\r\n> Hi Priya\r\n").encode()
        res = mailer.ingest(self.db, reply)
        self.assertEqual(res["lead_id"], lid)
        self.assertEqual(res["body"], "Sounds interesting, what does it cost?")
        self.assertEqual(self.db.lead(lid)["status"], "replied")
        self.assertEqual(self.db.message(fu["id"])["status"], "skipped")
        self.assertIsNone(mailer.ingest(self.db, reply))  # dedupe

        # agent replies in-thread; replies bypass window but not cap
        cli.main(["draft", str(lid), "--kind", "reply", "--reply-to", str(res["id"]), "--classification", "question",
                  "--body", "Depends on scope - easiest is a 15 min call: https://cal.test/sam", "--approve"])
        cli.main(["send", "--no-sleep"])
        self.assertEqual(len(FakeSMTP.received), 2)
        self.assertIn("In-Reply-To: <r1@rd.com>", FakeSMTP.received[1]["data"])
        self.assertNotIn("no thanks", FakeSMTP.received[1]["data"])  # no cold footer in warm replies
        self.assertEqual(self.db.message(res["id"])["status"], "handled")

        # daily cap (2) enforced: the first email was back-dated, so today = 1 sent; one more allowed, then stop
        cli.main(["draft", str(lid), "--kind", "reply", "--body", "third", "--approve"])
        cli.main(["draft", str(lid), "--kind", "reply", "--body", "fourth", "--approve"])
        cli.main(["send", "--no-sleep"])
        self.assertEqual(len(FakeSMTP.received), 3)
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM messages WHERE status='approved'")["n"], 1)

    def test_unsubscribe_and_bounce(self):
        lid, _ = self.db.upsert_lead({"name": "Acme", "domain": "acme.test"})
        self.db.add_contact(lid, "Bob", "Stone", email="bob@acme.test")
        self.db.update_lead(lid, status="contacted")
        self.db.add_message(lead_id=lid, direction="out", kind="initial", to_addr="bob@acme.test", subject="hi",
                            body="x", message_id="<o1@g>", status="sent", sent_at="2026-11-01T10:00:00+00:00")
        raw = b"From: bob@acme.test\r\nSubject: Re: hi\r\nMessage-ID: <u1@a>\r\nIn-Reply-To: <o1@g>\r\n\r\nPlease remove me.\r\n"
        res = mailer.ingest(self.db, raw)
        self.assertEqual(res["classification"], "unsubscribe")
        self.assertEqual(self.db.lead(lid)["status"], "unsubscribed")
        self.assertTrue(self.db.is_suppressed("bob@acme.test"))
        with self.assertRaises(SystemExit):
            cli.main(["draft", str(lid), "--subject", "again", "--body", "x"])

        lid2, _ = self.db.upsert_lead({"name": "Beta", "domain": "beta.test"})
        self.db.add_message(lead_id=lid2, direction="out", kind="initial", to_addr="jo@beta.test", subject="hi",
                            body="x", message_id="<o2@g>", status="sent", sent_at="2026-11-01T10:00:00+00:00")
        bounce = (b"From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>\r\nSubject: Delivery Status Notification\r\n"
                  b"Message-ID: <b1@g>\r\n\r\nFinal-Recipient: rfc822; jo@beta.test\r\nStatus: 5.1.1\r\n")
        mailer.ingest(self.db, bounce)
        self.assertEqual(self.db.lead(lid2)["status"], "bounced")
        self.assertTrue(self.db.is_suppressed("jo@beta.test"))

    def test_window(self):
        self.cfg["sending"].update({"window_hours": [9, 17], "weekdays_only": True})
        sat = datetime(2026, 10, 31, 10, 0).astimezone()
        self.assertFalse(mailer.window_ok(self.cfg, sat)[0])
        mon = datetime(2026, 11, 2, 10, 0).astimezone()
        self.assertTrue(mailer.window_ok(self.cfg, mon)[0])
        self.assertFalse(mailer.window_ok(self.cfg, mon.replace(hour=20))[0])


if __name__ == "__main__":
    unittest.main()
