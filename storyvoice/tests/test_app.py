import io
import os
import tempfile
import time

os.environ.setdefault("STORYVOICE_DATA", tempfile.mkdtemp())
os.environ["STORYVOICE_TTS"] = "espeak"  # offline engine for CI
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from app import mood, music, pdf_finder, transcribe
from app.main import app

client = TestClient(app)

HORROR = ("The corpse lay in the darkness. A scream echoed through the haunted house, "
          "and blood dripped from the cursed skull. Terror and dread filled the shadows.")
KIDS = "Once upon a time a tiny bunny met a magical fairy and a talking teddy under a rainbow."
SAD = "She wept at the funeral. The grief and sorrow of the loss left her lonely and heartbroken."


def test_mood_detection():
    assert mood.passage_mood(HORROR, "fiction") == "horror"
    assert mood.detect_genre(KIDS) == "children"
    assert mood.passage_mood(SAD, "fiction") == "sad"
    assert mood.detect_language("यह एक कहानी है जो बहुत पुरानी है") == "hi"


def test_story_mood_changes_by_passage():
    res = mood.analyse(f"{KIDS}\n\n{HORROR}\n\n{HORROR}", genre="fiction")
    moods = [p["mood"] for p in res["passages"]]
    assert "horror" in moods


def test_split_passages_limits_length():
    text = ("This is a sentence. " * 300).strip()
    parts = mood.split_passages(text, max_chars=500)
    assert len(parts) > 5 and all(len(p) <= 520 for p in parts)


def test_vtt_dedup():
    vtt = """WEBVTT

00:00:00.000 --> 00:00:02.000
hello world

00:00:02.000 --> 00:00:04.000
hello world

00:00:04.000 --> 00:00:06.000
<c>this is</c> a test
"""
    assert transcribe.vtt_to_text(vtt) == "hello world this is a test"


def test_segments_to_script_paragraphs():
    segs = [{"start": 0, "end": 1, "text": "Hi."}, {"start": 1.1, "end": 2, "text": "There."},
            {"start": 6, "end": 7, "text": "New part."}]
    assert transcribe.segments_to_script(segs) == "Hi. There.\n\nNew part."


def test_extract_pdf_links():
    html = '<a href="/books/alice.pdf">Alice in Wonderland</a><a href="x.html">no</a><a href="/b.PDF">PDF</a>'
    links = pdf_finder.extract_pdf_links(html, "https://site.org/list/")
    assert [l["url"] for l in links] == ["https://site.org/books/alice.pdf", "https://site.org/b.PDF"]
    assert links[0]["title"] == "Alice in Wonderland"


def test_ssrf_guard():
    with pytest.raises(pdf_finder.FetchError):
        pdf_finder._check_public_url("http://127.0.0.1:8000/x.pdf")
    with pytest.raises(pdf_finder.FetchError):
        pdf_finder._check_public_url("file:///etc/passwd")


def test_gutenberg_strip():
    t = "header\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nStory\n*** END OF THE PROJECT GUTENBERG EBOOK"
    assert pdf_finder.strip_gutenberg_boilerplate(t) == "Story"


def test_music_all_moods():
    for m in music.STYLES:
        x = music.render(m, 4.0)
        assert len(x) == 4 * music.SR and 0.3 < abs(x).max() <= 0.51
    bed = music.render_timeline([("calm", 3), ("horror", 3)])
    assert len(bed) == 6 * music.SR


def _make_pdf(text_pages):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for t in text_pages:
        c.drawString(72, 720, t)
        c.showPage()
    c.save()
    return buf.getvalue()


def _wait(job):
    for _ in range(300):
        j = client.get(f"/api/jobs/{job}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.3)
    raise TimeoutError


def test_pdf_upload_and_narrate_pages_with_music():
    pdf = _make_pdf(["Once upon a time a tiny bunny met a fairy.", "The ghost screamed in the darkness.",
                     "Page three is not read."])
    r = client.post("/api/pdf/upload", files={"file": ("tale.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["meta"]["pages"] == 3
    lib = client.get(f"/api/library/{item['id']}").json()
    assert lib["text"].count("\f") == 2

    r = client.post("/api/narrate", json={"item_id": item["id"], "page_from": 1, "page_to": 2, "music": True})
    j = _wait(r.json()["job"])
    assert j["status"] == "done", j
    res = j["result"]
    assert res["duration"] > 2
    assert "Page three" not in " ".join(s["text"] for s in res["timeline"])
    audio = client.get(res["audio"])
    assert audio.status_code == 200 and len(audio.content) > 5000


def test_script_crud_and_analyse():
    item = client.post("/api/library/script", json={"title": "Mine", "text": SAD}).json()
    a = client.post("/api/analyse", json={"item_id": item["id"]}).json()
    assert a["moods"].get("sad") and a["words"] > 10
    assert client.delete(f"/api/library/{item['id']}").json()["deleted"]


def test_reject_non_pdf_upload():
    r = client.post("/api/pdf/upload", files={"file": ("x.pdf", b"hello", "application/pdf")})
    assert r.status_code == 400


def test_music_preview_and_ui():
    assert client.get("/api/music/epic.wav?seconds=5").status_code == 200
    assert "StoryVoice" in client.get("/").text


def _scanned_pdf(lines):
    """Image-only PDF (no text layer), like a scanned book."""
    from PIL import Image, ImageDraw, ImageFont
    pages = []
    for line in lines:
        img = Image.new("RGB", (1240, 400), "white")
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 48)
        except OSError:
            font = ImageFont.load_default()
        d.text((60, 150), line, fill="black", font=font)
        pages.append(img)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:])
    return buf.getvalue()


def test_scanned_ia_book_gets_archive_text_and_narrates(monkeypatch):
    from app import library, ocr
    pdf = _scanned_pdf(["page one", "page two"])
    up = client.post("/api/pdf/upload", files={"file": ("gita.pdf", pdf, "application/pdf")}).json()
    assert ocr.needs_ocr(client.get(f"/api/library/{up['id']}").json()["text"])
    library.update_item(up["id"], source="https://archive.org/download/gita123/gita.pdf")
    story = "\n\n".join(["Arjuna stood on the battlefield, his bow trembling as the armies gathered. " * 3] * 4)
    monkeypatch.setattr(ocr, "fetch_ia_text", lambda ident: story if ident == "gita123" else "")
    r = client.post("/api/narrate", json={"item_id": up["id"], "page_from": 1, "page_to": 2, "music": False})
    assert r.status_code == 200, r.text
    j = _wait(r.json()["job"])
    assert j["status"] == "done", j
    assert "Arjuna" in j["result"]["timeline"][0]["text"]


def test_ia_identifier():
    from app import ocr
    assert ocr.ia_identifier("https://archive.org/download/abc_123/x.pdf") == "abc_123"
    assert ocr.ia_identifier("https://example.com/download/abc/x.pdf") is None


@pytest.mark.skipif(not __import__("shutil").which("tesseract"), reason="tesseract not installed")
def test_tesseract_ocr_reads_scanned_pages():
    pdf = _scanned_pdf(["The brave king rode into battle", "Hope returned to the kingdom"])
    up = client.post("/api/pdf/upload", files={"file": ("scan.pdf", pdf, "application/pdf")}).json()
    j = _wait(client.post(f"/api/library/{up['id']}/ocr?page_from=1&page_to=2").json()["job"])
    assert j["status"] == "done", j
    text = client.get(f"/api/library/{up['id']}").json()["text"].lower()
    assert "brave king" in text and "hope returned" in text


def test_locked_ia_pdf_falls_back_to_archive_text(monkeypatch):
    from app import ocr
    def locked(url, title=""):
        raise pdf_finder.FetchError("This Internet Archive book is borrow-only")
    monkeypatch.setattr(pdf_finder, "download_pdf", locked)
    monkeypatch.setattr(ocr, "fetch_ia_text", lambda ident: "Breathe in slowly and relax. " * 40)
    r = client.post("/api/pdf/download", json={"url": "ia:howtomeditate", "title": "How to Meditate"})
    assert r.status_code == 200, r.text
    assert "Breathe" in client.get(f"/api/library/{r.json()['id']}").json()["text"]


def test_locked_without_text_gives_clear_error(monkeypatch):
    from app import ocr
    monkeypatch.setattr(pdf_finder, "download_pdf",
                        lambda u, t="": (_ for _ in ()).throw(pdf_finder.FetchError("borrow-only")))
    monkeypatch.setattr(ocr, "fetch_ia_text", lambda ident: "")
    r = client.post("/api/pdf/download", json={"url": "ia:x", "title": "X"})
    assert r.status_code == 400 and "borrow-only" in r.json()["detail"]
